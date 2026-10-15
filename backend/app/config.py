import os


class Config:
    # All settings come from environment variables so the same image can run
    # locally, in docker-compose, and in Kubernetes (via ConfigMaps/Secrets).
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://shop:shop@localhost:5432/shop"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
