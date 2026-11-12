"""F06: reject unsafe deployment configuration without exposing credentials."""

import json
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings

TEST_KEY = secrets.token_hex(32)
TEST_DB_PASSWORD = secrets.token_urlsafe(24)


@pytest.fixture(autouse=True)
def isolated_config_environment(monkeypatch):
    for name in ("APP_ENV", "ENVIRONMENT", "SECRET_KEY", "DB_PASSWORD", "DEV_ALLOW_OPEN_ANYTIME"):
        monkeypatch.delenv(name, raising=False)


def configured(**values):
    return Settings(_env_file=None, **{
        "SECRET_KEY": TEST_KEY, "DB_PASSWORD": TEST_DB_PASSWORD, **values,
    })


@pytest.mark.parametrize("key", [None, "", "   ", "change-this-to-a-random-64-char-secret", "F06_SHORT_SENTINEL",
                                 "a" * 64, " " + TEST_KEY, TEST_KEY + " "])
def test_production_rejects_missing_default_or_short_secret(key):
    values = {"APP_ENV": "production", "DB_PASSWORD": TEST_DB_PASSWORD}
    if key is not None:
        values["SECRET_KEY"] = key
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


@pytest.mark.parametrize("password", ["", "   ", "changeme", "rootpassword", "password"])
def test_production_rejects_default_database_password(password):
    with pytest.raises(ValidationError):
        configured(APP_ENV="production", DB_PASSWORD=password)


@pytest.mark.parametrize("environment", ["production", " Production ", "PRODUCTION"])
def test_production_accepts_generated_credentials(environment):
    settings = configured(APP_ENV=environment)
    assert settings.APP_ENV == "production"
    assert settings.SECRET_KEY == TEST_KEY


def test_legacy_environment_cannot_silently_select_development():
    assert configured(ENVIRONMENT=" Production ").APP_ENV == "production"
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ENVIRONMENT="production")
    with pytest.raises(ValidationError):
        configured(APP_ENV="development", ENVIRONMENT="production")
    assert configured(APP_ENV="production", ENVIRONMENT="production").APP_ENV == "production"


@pytest.mark.parametrize("environment", ["prodution", "prod", "", "staging"])
def test_environment_typo_is_rejected(environment):
    with pytest.raises(ValidationError):
        configured(APP_ENV=environment)


def test_development_and_test_preserve_local_workflow():
    for environment in ("development", "test"):
        settings = Settings(_env_file=None, APP_ENV=environment)
        assert environment == settings.APP_ENV
    assert configured(APP_ENV="development", DEV_ALLOW_OPEN_ANYTIME=True).DEV_ALLOW_OPEN_ANYTIME


def test_production_rejects_demo_open_override():
    with pytest.raises(ValidationError):
        configured(APP_ENV="production", DEV_ALLOW_OPEN_ANYTIME=True)


def test_configuration_repr_and_validation_errors_hide_credentials():
    settings = configured()
    assert TEST_KEY not in repr(settings)
    assert TEST_DB_PASSWORD not in repr(settings)
    with pytest.raises(ValidationError) as error:
        configured(APP_ENV="production", DEV_ALLOW_OPEN_ANYTIME=True)
    assert TEST_KEY not in str(error.value)
    assert TEST_DB_PASSWORD not in str(error.value)


def test_unsafe_process_stops_before_database_or_scheduler_import(tmp_path):
    env = os.environ.copy()
    env.update(APP_ENV="production", SECRET_KEY="F06_SHORT_SENTINEL",
               DB_PASSWORD=TEST_DB_PASSWORD, PYTHONIOENCODING="utf-8",
               PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    script = '''
import sys
class BlockResources:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith('app.db') or fullname == 'app.services.scheduler':
            raise RuntimeError('UNSAFE_RESOURCE_IMPORT')
sys.meta_path.insert(0, BlockResources())
import app.main
print('APP_IMPORTED')
'''
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env=env,
                            capture_output=True, encoding="utf-8", timeout=30, check=False)
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "APP_IMPORTED" not in output
    assert "UNSAFE_RESOURCE_IMPORT" not in output
    assert "F06_SHORT_SENTINEL" not in output
    assert TEST_DB_PASSWORD not in output


def test_valid_production_process_serves_health(tmp_path):
    env = os.environ.copy()
    env.update(APP_ENV="production", SECRET_KEY=TEST_KEY, DB_PASSWORD=TEST_DB_PASSWORD,
               DB_HOST="127.0.0.1", DB_PORT="1", PYTHONIOENCODING="utf-8",
               PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    script = '''
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
with patch('app.main.start_scheduler'), patch('app.main.stop_scheduler'), TestClient(app) as client:
    assert client.get('/health').json()['status'] == 'ok'
print('PRODUCTION_HEALTH_OK')
'''
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env=env,
                            capture_output=True, encoding="utf-8", timeout=30, check=False)
    assert result.returncode == 0
    assert "PRODUCTION_HEALTH_OK" in result.stdout
    assert TEST_KEY not in result.stdout + result.stderr
    assert TEST_DB_PASSWORD not in result.stdout + result.stderr


@pytest.mark.parametrize("names", [
    {"APP_ENV": "production"}, {"ENVIRONMENT": " Production "},
])
def test_production_seed_refuses_before_creating_database_session(tmp_path, names):
    env = os.environ.copy()
    env.update(names, SECRET_KEY=TEST_KEY, DB_PASSWORD=TEST_DB_PASSWORD,
               DB_HOST="127.0.0.1", DB_PORT="1", PYTHONIOENCODING="utf-8")
    script = Path(__file__).resolve().parents[2] / "scripts" / "seed.py"
    result = subprocess.run([sys.executable, str(script)], cwd=tmp_path, env=env,
                            capture_output=True, encoding="utf-8", timeout=30, check=False)
    assert result.returncode == 1
    assert "Production" in result.stdout
    assert "OperationalError" not in result.stderr
    assert TEST_KEY not in result.stdout + result.stderr
    assert TEST_DB_PASSWORD not in result.stdout + result.stderr


@pytest.fixture
def compose_config(tmp_path):
    if shutil.which("docker") is None:
        pytest.skip("Docker Compose is required for rendered deployment configuration tests")
    source = Path(__file__).resolve().parents[2] / "docker-compose.yml"
    shutil.copyfile(source, tmp_path / "docker-compose.yml")
    for folder in ("backend", "frontend", "scripts", "uploads"):
        (tmp_path / folder).mkdir()

    def render(missing=None):
        values = {"DB_PASSWORD": TEST_DB_PASSWORD, "MYSQL_ROOT_PASSWORD": secrets.token_urlsafe(24),
                  "SECRET_KEY": TEST_KEY, "APP_ENV": "development", "DB_PORT": "3307"}
        if missing:
            values.pop(missing)
        (tmp_path / ".env").write_text("\n".join(f"{key}={value}" for key, value in values.items()), encoding="utf-8")
        env = os.environ.copy()
        for key in (*Settings.model_fields, "MYSQL_ROOT_PASSWORD", "COMPOSE_FILE", "COMPOSE_PROJECT_NAME"):
            env.pop(key, None)
        return subprocess.run(["docker", "compose", "--env-file", str(tmp_path / ".env"),
                               "-f", str(tmp_path / "docker-compose.yml"), "config", "--format", "json"],
                              cwd=tmp_path, env=env, capture_output=True, encoding="utf-8",
                              timeout=30, check=False)

    return render


def test_compose_keeps_dev_ports_local_and_credentials_consistent(compose_config):
    result = compose_config()
    assert result.returncode == 0
    services = json.loads(result.stdout)["services"]
    for name in ("mysql", "backend", "frontend"):
        assert all(port["host_ip"] == "127.0.0.1" for port in services[name]["ports"])
    assert services["mysql"]["environment"]["MYSQL_PASSWORD"] == TEST_DB_PASSWORD
    assert services["backend"]["environment"]["DB_PASSWORD"] == TEST_DB_PASSWORD
    assert str(services["backend"]["environment"]["DB_PORT"]) == "3306"
    assert services["backend"]["environment"]["SECRET_KEY"] == TEST_KEY
    assert services["backend"]["environment"]["MYSQL_ROOT_PASSWORD"] == ""
    healthcheck = str(services["mysql"]["healthcheck"])
    assert TEST_DB_PASSWORD not in healthcheck
    assert "MYSQL_PASSWORD" in healthcheck


@pytest.mark.parametrize("missing", ["DB_PASSWORD", "MYSQL_ROOT_PASSWORD", "SECRET_KEY"])
def test_compose_refuses_missing_credentials(compose_config, missing):
    result = compose_config(missing)
    assert result.returncode != 0
    assert missing in result.stderr
    assert TEST_KEY not in result.stderr
    assert TEST_DB_PASSWORD not in result.stderr
