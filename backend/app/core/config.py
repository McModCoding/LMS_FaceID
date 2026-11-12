from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True,
    )
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "lms_user"
    DB_PASSWORD: str = Field(default="changeme", repr=False)
    DB_NAME: str = "lms_db"
    SECRET_KEY: str = Field(default="change-this-to-a-random-64-char-secret", repr=False)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    FACE_ENGINE: str = "mock"
    FACE_MIN_HITS: int = Field(default=3, ge=1)
    FACE_MATCH_THRESHOLD: float = Field(default=0.0, allow_inf_nan=False)  # phải hiệu chỉnh thực nghiệm khi dùng engine thật
    FACE_MARGIN_THRESHOLD: float = Field(default=0.0, allow_inf_nan=False)  # phải hiệu chỉnh thực nghiệm khi dùng engine thật
    FACE_STORAGE_DIR: str = "data/face"
    # M9a — engine OpenCV (YuNet + SFace). Trọng số tải bằng face_tools/download_face_models.py,
    # không đóng gói theo mã nguồn. Các ngưỡng chất lượng là heuristic, cần hiệu chỉnh theo camera.
    FACE_MODELS_DIR: str = "models/face"
    FACE_YUNET_MODEL: str = "face_detection_yunet_2023mar.onnx"
    FACE_SFACE_MODEL: str = "face_recognition_sface_2021dec.onnx"
    FACE_EMBEDDING_KEY: str = Field(default="", repr=False)  # khóa Fernet; trống = không mã hóa embedding
    FACE_DETECT_SCORE: float = Field(default=0.7, gt=0, le=1, allow_inf_nan=False)
    FACE_MIN_FACE_PIXELS: int = Field(default=100, ge=32)           # đăng ký ảnh
    FACE_IDENTIFY_MIN_FACE_PIXELS: int = Field(default=64, ge=32)   # nhận diện khung lớp học
    FACE_MIN_FACE_BLUR: float = Field(default=40.0, ge=0, allow_inf_nan=False)
    FACE_MIN_CONTRAST: float = Field(default=19.0, ge=0, allow_inf_nan=False)
    FACE_MAX_FACES_PER_FRAME: int = Field(default=20, ge=1, le=100)
    UPLOAD_STORAGE_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 10
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15
    EXAM_GRACE_SECONDS: int = Field(default=5, ge=0, le=5)

    # M3a — Vòng đời buổi học
    SESSION_OPEN_BEFORE_MIN: int = 30       # mở trước giờ bắt đầu (phút)
    SESSION_OPEN_AFTER_END_MIN: int = 60    # mở muộn nhất sau giờ kết thúc (phút)
    SESSION_AUTO_CLOSE_AFTER_END_MIN: int = 120  # tự đóng sau giờ kết thúc (phút)
    EDIT_AFTER_CLOSE_HOURS: int = 24        # cửa sổ GV sửa điểm danh sau khi đóng (giờ)
    DEV_ALLOW_OPEN_ANYTIME: bool = False    # CHỈ demo — mặc định tắt
    APP_ENV: Literal["development", "test", "production"] = "development"
    # Compatibility only. Conflicting names must not silently bypass safeguards.
    ENVIRONMENT: Literal["development", "test", "production"] | None = Field(
        default=None, exclude=True, repr=False,
    )

    @field_validator("APP_ENV", "ENVIRONMENT", mode="before")
    @classmethod
    def normalize_environment(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_deployment(self):
        if self.ENVIRONMENT is not None:
            if "APP_ENV" in self.model_fields_set and self.APP_ENV != self.ENVIRONMENT:
                raise ValueError("APP_ENV và ENVIRONMENT mâu thuẫn. Chỉ dùng APP_ENV hoặc đặt cùng giá trị.")
            self.APP_ENV = self.ENVIRONMENT
        if self.APP_ENV == "production":
            if (
                self.SECRET_KEY.strip() != self.SECRET_KEY
                or len(self.SECRET_KEY) < 64
                or len(set(self.SECRET_KEY)) == 1
            ):
                raise ValueError("Production yêu cầu SECRET_KEY riêng, sinh ngẫu nhiên, tối thiểu 64 ký tự; không dùng giá trị mẫu.")
            if self.DB_PASSWORD.strip().lower() in {"", "changeme", "rootpassword", "password"}:
                raise ValueError("Production yêu cầu DB_PASSWORD riêng; không dùng mật khẩu trống hoặc mặc định.")
            if self.DEV_ALLOW_OPEN_ANYTIME:
                raise ValueError("Production yêu cầu DEV_ALLOW_OPEN_ANYTIME=false.")
            if self.FACE_ENGINE == "opencv" and not self.FACE_EMBEDDING_KEY.strip():
                raise ValueError("Production với FACE_ENGINE=opencv yêu cầu FACE_EMBEDDING_KEY để mã hóa embedding.")
        if self.FACE_EMBEDDING_KEY.strip():
            try:
                from cryptography.fernet import Fernet

                Fernet(self.FACE_EMBEDDING_KEY.strip().encode())
            except Exception:  # noqa: BLE001 - không in giá trị khóa
                raise ValueError(
                    "FACE_EMBEDDING_KEY không hợp lệ; sinh khóa bằng "
                    "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
                ) from None
        return self

    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
    @property
    def SYNC_DATABASE_URL(self) -> str:
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
