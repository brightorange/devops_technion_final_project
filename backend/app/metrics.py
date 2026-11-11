"""Prometheus instrumentation.

Gunicorn runs several worker processes per pod, each with its own memory. A
naive setup therefore reports whichever worker the scrape happened to reach.
Setting PROMETHEUS_MULTIPROC_DIR makes prometheus_client write counters to
mmapped files in that directory instead, so /metrics aggregates across all
workers in the pod. Without the variable set (tests, `flask run`) the ordinary
single-process collector is used.
"""

import os

from prometheus_client import Counter, Histogram

ORDERS_CREATED = Counter(
    "shop_orders_created_total",
    "Orders successfully placed.",
)

ORDERS_REJECTED = Counter(
    "shop_orders_rejected_total",
    "Orders that could not be placed.",
    ["reason"],
)

ORDER_VALUE = Histogram(
    "shop_order_value",
    "Value of a placed order.",
    # Tuned to the catalogue's price range rather than the library defaults,
    # which top out at 10 and would put every order in the same bucket.
    buckets=(10, 50, 100, 250, 500, 1000, 2500, float("inf")),
)

ITEMS_SOLD = Counter(
    "shop_items_sold_total",
    "Individual units sold, across all orders.",
)


def init_metrics(app):
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        from prometheus_flask_exporter.multiprocess import (
            GunicornInternalPrometheusMetrics as Metrics,
        )
    else:
        from prometheus_flask_exporter import PrometheusMetrics as Metrics

    # group_by="url_rule" keeps the label at /api/products/<int:product_id>
    # rather than one time series per product id, which would grow without bound.
    # The prefix is "shop", not "shop_http": the default metric names already
    # begin with http_, giving shop_http_request_total.
    return Metrics(app, group_by="url_rule", defaults_prefix="shop")
