from decimal import Decimal

from flask_restful import Resource, abort

from ..extensions import db
from ..models import CartItem, Order, OrderItem, Product
from ..validation import fail_if, json_body, positive_int


class OrderList(Resource):
    def post(self):
        data = json_body()
        errors = {}
        user_id = positive_int(data, "user_id", errors)
        fail_if(errors)

        cart = db.session.scalars(db.select(CartItem).filter_by(user_id=user_id)).all()
        if not cart:
            abort(400, message=f"Cart of user {user_id} is empty")

        # Lock the product rows (SELECT ... FOR UPDATE) so two simultaneous
        # orders can't both buy the last item in stock.
        product_ids = [item.product_id for item in cart]
        products = {
            product.id: product
            for product in db.session.scalars(
                db.select(Product).where(Product.id.in_(product_ids)).with_for_update()
            )
        }

        order = Order(user_id=user_id, total=Decimal("0"))
        for item in cart:
            product = products[item.product_id]
            if item.quantity > product.stock:
                db.session.rollback()
                abort(409, message=f"Only {product.stock} of product {product.id} in stock")
            product.stock -= item.quantity
            order.items.append(
                OrderItem(product_id=product.id, quantity=item.quantity, unit_price=product.price)
            )
            order.total += product.price * item.quantity
            db.session.delete(item)

        # Stock change, new order and emptied cart are committed together or not at all.
        db.session.add(order)
        db.session.commit()
        return order.to_dict(), 201


class OrderDetail(Resource):
    def get(self, order_id):
        order = db.session.get(Order, order_id)
        if order is None:
            abort(404, message=f"Order {order_id} not found")
        return order.to_dict(), 200
