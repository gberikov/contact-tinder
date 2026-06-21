FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    "fastapi" "uvicorn[standard]" "sqlalchemy>=2.0" "alembic>=1.13" \
    "psycopg[binary]>=3.2" "pydantic>=2.7" "pydantic-settings>=2.3" "cryptography>=42.0" \
    "google-api-python-client>=2.130" "google-auth-oauthlib>=1.2" "google-auth>=2.30" \
    "phonenumbers>=8.13" "email-validator>=2.1" "httpx>=0.27"

COPY . .

EXPOSE 8000
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
