from decimal import Decimal

from flask import Response
from flask_restful import Resource, abort

from ..extensions import db
from ..models import CartItem
from ..validation import fail_if, json_body, positive_int
from .products import get_product_or_404


def find_cart_item(user_id, product_id):
    return db.session.scalar(
        db.select(CartItem).filter_by(user_id=user_id, product_id=product_id)
    )


class Cart(Resource):
    def post(self):
        data = json_body()
        errors = {}
        user_id = positive_int(data, "user_id", errors)
        product_id = positive_int(data, "product_id", errors)
        quantity = positive_int(data, "quantity", errors)
        fail_if(errors)

        product = get_product_or_404(product_id)
        item = find_cart_item(user_id, product_id)
        created = item is None
        new_quantity = quantity + (0 if created else item.quantity)
        if new_quantity > product.stock:
            abort(409, message=f"Only {product.stock} of product {product_id} in stock")

        if created:
            item = CartItem(user_id=user_id, product_id=product_id, product=product)
            db.session.add(item)
        item.quantity = new_quantity
        db.session.commit()
        return item.to_dict(), 201 if created else 200


class UserCart(Resource):
    def get(self, user_id):
        items = db.session.scalars(
            db.select(CartItem).filter_by(user_id=user_id).order_by(CartItem.id)
        ).all()
        total = sum((item.product.price * item.quantity for item in items), Decimal("0"))
        return {
            "user_id": user_id,
            "items": [item.to_dict() for item in items],
            "total": float(total),
        }, 200


class UserCartItem(Resource):
    def delete(self, user_id, product_id):
        item = find_cart_item(user_id, product_id)
        if item is None:
            abort(404, message=f"Product {product_id} is not in the cart of user {user_id}")
        db.session.delete(item)
        db.session.commit()
        return Response(status=204)
