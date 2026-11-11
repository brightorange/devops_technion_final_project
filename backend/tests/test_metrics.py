from flask import Flask

from app.metrics import init_metrics


def test_single_process_collector_by_default(monkeypatch):
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    metrics = init_metrics(Flask(__name__))
    assert type(metrics).__name__ == "PrometheusMetrics"


def test_multiprocess_collector_when_configured(monkeypatch, tmp_path):
    # Under gunicorn each worker has its own memory, so metrics must be
    # collected from shared files instead of the process-local registry.
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path))
    metrics = init_metrics(Flask(__name__))
    assert type(metrics).__name__ == "GunicornInternalPrometheusMetrics"


def test_metrics_endpoint_exposes_custom_business_metrics(client, make_product, add_to_cart):
    product = make_product(price=100, stock=5)
    add_to_cart(user_id=1, product_id=product["id"], quantity=2)
    assert client.post("/api/orders", json={"user_id": 1}).status_code == 201

    body = client.get("/metrics").get_data(as_text=True)
    assert "shop_orders_created_total" in body
    assert "shop_items_sold_total" in body
    assert "shop_order_value" in body
