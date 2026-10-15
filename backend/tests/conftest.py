import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db


@pytest.fixture
def app():
    # Every test gets fresh, empty tables, so tests can't affect each other.
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def make_product(client):
    def _make(name="Laptop", price=999.99, stock=3):
        response = client.post(
            "/api/products", json={"name": name, "price": price, "stock": stock}
        )
        assert response.status_code == 201
        return response.get_json()

    return _make


@pytest.fixture
def add_to_cart(client):
    def _add(product_id, quantity=1, user_id=1):
        return client.post(
            "/api/cart",
            json={"user_id": user_id, "product_id": product_id, "quantity": quantity},
        )

    return _add
