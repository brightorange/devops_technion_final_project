import os

from sqlalchemy.engine import URL


def database_url():
    # A full DATABASE_URL wins (used by docker-compose). Otherwise build it from
    # parts, so Kubernetes can supply host/name via a ConfigMap and
    # user/password via a Secret.
    if url := os.environ.get("DATABASE_URL"):
        return url
    # URL.create escapes special characters, so a password like "p@ss/word"
    # can't break the connection string.
    return URL.create(
        "postgresql+psycopg",
        username=os.environ.get("DB_USER", "shop"),
        password=os.environ.get("DB_PASSWORD", "shop"),
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        database=os.environ.get("DB_NAME", "shop"),
    )


class Config:
    # All settings come from environment variables so the same image can run
    # locally, in docker-compose, and in Kubernetes (via ConfigMaps/Secrets).
    SQLALCHEMY_DATABASE_URI = database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class TestConfig(Config):
    TESTING = True
    # Fast in-memory SQLite by default; set TEST_DATABASE_URL to run against Postgres.
    SQLALCHEMY_DATABASE_URI = os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")
