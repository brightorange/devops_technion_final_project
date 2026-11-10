from app.config import database_url


def test_database_url_env_wins(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://a:b@db:5432/x")
    monkeypatch.setenv("DB_HOST", "ignored")
    assert database_url() == "postgresql+psycopg://a:b@db:5432/x"


def test_database_url_from_parts(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_USER", "shop")
    monkeypatch.setenv("DB_PASSWORD", "secret")
    monkeypatch.setenv("DB_HOST", "postgres")
    monkeypatch.setenv("DB_PORT", "5433")
    monkeypatch.setenv("DB_NAME", "shopdb")

    url = database_url()
    assert (url.host, url.port, url.database) == ("postgres", 5433, "shopdb")
    assert (url.username, url.password) == ("shop", "secret")


def test_database_url_escapes_special_characters(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_PASSWORD", "p@ss/word:1")

    rendered = database_url().render_as_string(hide_password=False)
    assert "p%40ss%2Fword%3A1" in rendered
