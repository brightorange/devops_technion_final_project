def test_place_order(client, add_to_cart, make_product):
    laptop = make_product(price=999.99, stock=3)
    mouse = make_product(name="Mouse", price=25, stock=10)
    add_to_cart(laptop["id"], quantity=2)
    add_to_cart(mouse["id"], quantity=1)

    response = client.post("/api/orders", json={"user_id": 1})
    assert response.status_code == 201
    order = response.get_json()
    assert order["status"] == "pending"
    assert order["total"] == 2024.98
    assert len(order["items"]) == 2


def test_order_reduces_stock_and_empties_cart(client, add_to_cart, make_product):
    product = make_product(stock=3)
    add_to_cart(product["id"], quantity=2)
    client.post("/api/orders", json={"user_id": 1})

    assert client.get("/api/products").get_json()[0]["stock"] == 1
    assert client.get("/api/cart/1").get_json()["items"] == []


def test_order_keeps_price_at_purchase_time(client, add_to_cart, make_product):
    product = make_product(price=100)
    add_to_cart(product["id"])
    order = client.post("/api/orders", json={"user_id": 1}).get_json()

    client.put(f"/api/products/{product['id']}", json={"price": 150})

    saved = client.get(f"/api/orders/{order['id']}").get_json()
    assert saved["items"][0]["unit_price"] == 100
    assert saved["total"] == 100


def test_order_with_empty_cart(client):
    response = client.post("/api/orders", json={"user_id": 1})
    assert response.status_code == 400


def test_order_fails_when_stock_ran_out(client, add_to_cart, make_product):
    # Stock dropped after the item was added to the cart.
    product = make_product(stock=3)
    add_to_cart(product["id"], quantity=3)
    client.put(f"/api/products/{product['id']}", json={"stock": 1})

    response = client.post("/api/orders", json={"user_id": 1})
    assert response.status_code == 409
    # Nothing changed: stock untouched, cart still full.
    assert client.get("/api/products").get_json()[0]["stock"] == 1
    assert len(client.get("/api/cart/1").get_json()["items"]) == 1


def test_order_validation(client):
    response = client.post("/api/orders", json={"user_id": "abc"})
    assert response.status_code == 400


def test_get_missing_order(client):
    assert client.get("/api/orders/42").status_code == 404
