def test_empty_cart(client):
    response = client.get("/api/cart/1")
    assert response.status_code == 200
    assert response.get_json() == {"user_id": 1, "items": [], "total": 0.0}


def test_add_to_cart(add_to_cart, make_product):
    product = make_product()
    response = add_to_cart(product["id"], quantity=2)
    assert response.status_code == 201
    assert response.get_json()["quantity"] == 2


def test_adding_same_product_increases_quantity(add_to_cart, make_product):
    product = make_product(stock=5)
    add_to_cart(product["id"], quantity=2)
    response = add_to_cart(product["id"], quantity=2)
    assert response.status_code == 200
    assert response.get_json()["quantity"] == 4


def test_cannot_add_more_than_stock(add_to_cart, make_product):
    product = make_product(stock=3)
    add_to_cart(product["id"], quantity=2)
    response = add_to_cart(product["id"], quantity=2)
    assert response.status_code == 409


def test_add_missing_product(add_to_cart):
    assert add_to_cart(product_id=99).status_code == 404


def test_add_to_cart_validation(client):
    response = client.post("/api/cart", json={"user_id": 0, "product_id": "1", "quantity": -1})
    assert response.status_code == 400
    assert set(response.get_json()["errors"]) == {"user_id", "product_id", "quantity"}


def test_cart_total(client, add_to_cart, make_product):
    laptop = make_product(price=999.99)
    mouse = make_product(name="Mouse", price=25, stock=10)
    add_to_cart(laptop["id"], quantity=2)
    add_to_cart(mouse["id"], quantity=1)

    cart = client.get("/api/cart/1").get_json()
    assert len(cart["items"]) == 2
    assert cart["total"] == 2024.98


def test_carts_are_per_user(client, add_to_cart, make_product):
    product = make_product()
    add_to_cart(product["id"], user_id=1)
    assert client.get("/api/cart/2").get_json()["items"] == []


def test_remove_from_cart(client, add_to_cart, make_product):
    product = make_product()
    add_to_cart(product["id"])
    response = client.delete(f"/api/cart/1/item/{product['id']}")
    assert response.status_code == 204
    assert client.get("/api/cart/1").get_json()["items"] == []


def test_remove_item_not_in_cart(client):
    assert client.delete("/api/cart/1/item/1").status_code == 404
