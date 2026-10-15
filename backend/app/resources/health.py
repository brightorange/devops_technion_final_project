from flask_restful import Resource
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db


class Liveness(Resource):
    """Is the process alive? Kubernetes restarts the pod if this fails."""

    def get(self):
        return {"status": "alive"}, 200


class Readiness(Resource):
    """Can we serve traffic? Kubernetes stops routing to the pod if this fails."""

    def get(self):
        try:
            db.session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return {"status": "not ready", "database": "unreachable"}, 503
        return {"status": "ready", "database": "ok"}, 200
