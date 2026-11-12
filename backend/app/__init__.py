from flask import Flask, send_from_directory
from flask_restful import Api

from .config import Config
from .extensions import db, migrate
from .metrics import init_metrics


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    init_metrics(app)

    db.init_app(app)
    migrate.init_app(app, db)
    from . import models  # noqa: F401  (registers tables for Flask-Migrate)

    from .resources.cart import Cart, UserCart, UserCartItem
    from .resources.health import Liveness, Readiness
    from .resources.orders import OrderDetail, OrderList
    from .resources.products import ProductDetail, ProductList

    # catch_all_404s: unknown URLs also get a JSON error instead of an HTML page.
    api = Api(app, catch_all_404s=True)
    api.add_resource(Liveness, "/health/live")
    api.add_resource(Readiness, "/health/ready")
    api.add_resource(ProductList, "/api/products")
    api.add_resource(ProductDetail, "/api/products/<int:product_id>")
    api.add_resource(Cart, "/api/cart")
    api.add_resource(UserCart, "/api/cart/<int:user_id>")
    api.add_resource(UserCartItem, "/api/cart/<int:user_id>/item/<int:product_id>")
    api.add_resource(OrderList, "/api/orders")
    api.add_resource(OrderDetail, "/api/orders/<int:order_id>")

    # Served under /ui rather than / so the ingress can route it explicitly.
    # A "/" prefix rule would match every path, including /health/*, and undo
    # the deliberate decision to keep the probes unreachable from outside.
    @app.get("/ui")
    def ui():
        return send_from_directory(app.static_folder, "index.html")

    return app
