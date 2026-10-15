from datetime import datetime, timezone

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    price = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "price": float(self.price),
            "stock": self.stock,
        }


class CartItem(db.Model):
    __tablename__ = "cart_items"
    # A user has at most one row per product; adding again increases quantity.
    __table_args__ = (db.UniqueConstraint("user_id", "product_id"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

    product = db.relationship("Product")

    def to_dict(self):
        return {
            "product_id": self.product_id,
            "name": self.product.name,
            "unit_price": float(self.product.price),
            "quantity": self.quantity,
        }


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="pending")
    total = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    items = db.relationship("OrderItem", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "status": self.status,
            "total": float(self.total),
            "items": [item.to_dict() for item in self.items],
        }


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    # Price is copied at order time so later price changes don't rewrite history.
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)

    def to_dict(self):
        return {
            "product_id": self.product_id,
            "quantity": self.quantity,
            "unit_price": float(self.unit_price),
        }
