FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y default-libmysqlclient-dev gcc curl && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
COPY app ./app
RUN pip install --no-cache-dir -e ".[dev,face]"
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
