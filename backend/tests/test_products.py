def test_list_is_empty_initially(client):
    response = client.get("/api/products")
    assert response.status_code == 200
    assert response.get_json() == []


def test_create_product(client):
    response = client.post(
        "/api/products",
        json={"name": "  Laptop  ", "description": "14 inch", "price": 999.99, "stock": 3},
    )
    assert response.status_code == 201
    assert response.get_json() == {
        "id": 1,
        "name": "Laptop",
        "description": "14 inch",
        "price": 999.99,
        "stock": 3,
    }


def test_create_product_defaults(client):
    response = client.post("/api/products", json={"name": "Pen", "price": 2})
    assert response.status_code == 201
    assert response.get_json()["stock"] == 0
    assert response.get_json()["description"] == ""


def test_create_product_reports_all_errors(client):
    response = client.post(
        "/api/products", json={"name": "", "description": 5, "price": -1, "stock": True}
    )
    assert response.status_code == 400
    assert set(response.get_json()["errors"]) == {"name", "description", "price", "stock"}


def test_create_product_requires_json_object(client):
    response = client.post("/api/products", data="not json", content_type="application/json")
    assert response.status_code == 400

    response = client.post("/api/products", json=["a", "list"])
    assert response.status_code == 400


def test_update_product(client, make_product):
    product = make_product()
    response = client.put(f"/api/products/{product['id']}", json={"price": 899, "stock": 10})
    assert response.status_code == 200
    assert response.get_json()["price"] == 899
    assert response.get_json()["stock"] == 10
    assert response.get_json()["name"] == "Laptop"


def test_update_product_rejects_empty_body(client, make_product):
    product = make_product()
    response = client.put(f"/api/products/{product['id']}", json={})
    assert response.status_code == 400


def test_update_missing_product(client):
    response = client.put("/api/products/99", json={"price": 1})
    assert response.status_code == 404


def test_delete_product(client, make_product):
    product = make_product()
    response = client.delete(f"/api/products/{product['id']}")
    assert response.status_code == 204
    assert client.get("/api/products").get_json() == []


def test_delete_product_removes_it_from_carts(client, make_product, add_to_cart):
    product = make_product()
    add_to_cart(product["id"])
    client.delete(f"/api/products/{product['id']}")
    assert client.get("/api/cart/1").get_json()["items"] == []


def test_cannot_delete_ordered_product(client, make_product, add_to_cart):
    product = make_product()
    add_to_cart(product["id"])
    client.post("/api/orders", json={"user_id": 1})

    response = client.delete(f"/api/products/{product['id']}")
    assert response.status_code == 409


def test_delete_missing_product(client):
    assert client.delete("/api/products/99").status_code == 404
