from flask import Response
from flask_restful import Resource, abort

from ..extensions import db
from ..models import CartItem, OrderItem, Product
from ..validation import fail_if, json_body, parse_product


def get_product_or_404(product_id):
    product = db.session.get(Product, product_id)
    if product is None:
        abort(404, message=f"Product {product_id} not found")
    return product


class ProductList(Resource):
    def get(self):
        products = db.session.scalars(db.select(Product).order_by(Product.id))
        return [product.to_dict() for product in products], 200

    def post(self):
        fields, errors = parse_product(json_body())
        fail_if(errors)
        product = Product(**fields)
        db.session.add(product)
        db.session.commit()
        return product.to_dict(), 201


class ProductDetail(Resource):
    def put(self, product_id):
        product = get_product_or_404(product_id)
        fields, errors = parse_product(json_body(), partial=True)
        fail_if(errors)
        for key, value in fields.items():
            setattr(product, key, value)
        db.session.commit()
        return product.to_dict(), 200

    def delete(self, product_id):
        product = get_product_or_404(product_id)
        # Past orders must keep pointing at the product they were placed for.
        ordered = db.session.scalar(
            db.select(OrderItem.id).where(OrderItem.product_id == product_id).limit(1)
        )
        if ordered:
            abort(409, message=f"Product {product_id} has orders and cannot be deleted")
        db.session.execute(db.delete(CartItem).where(CartItem.product_id == product_id))
        db.session.delete(product)
        db.session.commit()
        return Response(status=204)
