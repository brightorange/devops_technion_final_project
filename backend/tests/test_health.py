from sqlalchemy.exc import OperationalError

from app.extensions import db


def test_liveness(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.get_json() == {"status": "alive"}


def test_readiness_ok(client):
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.get_json()["database"] == "ok"


def test_readiness_fails_when_database_is_down(client, monkeypatch):
    def database_down(*args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr(db.session, "execute", database_down)

    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.get_json()["database"] == "unreachable"


def test_unknown_url_returns_json_404(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert "message" in response.get_json()
