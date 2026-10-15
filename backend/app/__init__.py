from flask import Flask
from flask_restful import Api

from .config import Config
from .extensions import db, migrate


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    from . import models  # noqa: F401  (registers tables for Flask-Migrate)

    from .resources.health import Liveness, Readiness

    api = Api(app)
    api.add_resource(Liveness, "/health/live")
    api.add_resource(Readiness, "/health/ready")

    return app
