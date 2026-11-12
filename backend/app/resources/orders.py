from decimal import Decimal

from flask import request
from flask_restful import Resource, abort

from ..extensions import db
from ..metrics import ITEMS_SOLD, ORDER_VALUE, ORDERS_CREATED, ORDERS_REJECTED
from ..models import CartItem, Order, OrderItem, Product
from ..validation import fail_if, json_body, positive_int


class OrderList(Resource):
    def get(self):
        """List orders, newest first, optionally for one user."""
        query = db.select(Order).order_by(Order.id.desc())
        user_id = request.args.get("user_id", type=int)
        if user_id is not None:
            query = query.filter_by(user_id=user_id)
        return [order.to_dict() for order in db.session.scalars(query)], 200

    def post(self):
        data = json_body()
        errors = {}
        user_id = positive_int(data, "user_id", errors)
        fail_if(errors)

        cart = db.session.scalars(db.select(CartItem).filter_by(user_id=user_id)).all()
        if not cart:
            ORDERS_REJECTED.labels(reason="empty_cart").inc()
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
                ORDERS_REJECTED.labels(reason="out_of_stock").inc()
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

        # Counted after the commit, so the metrics only ever reflect orders
        # that actually exist.
        ORDERS_CREATED.inc()
        ORDER_VALUE.observe(float(order.total))
        ITEMS_SOLD.inc(sum(item.quantity for item in order.items))

        return order.to_dict(), 201


class OrderDetail(Resource):
    def get(self, order_id):
        order = db.session.get(Order, order_id)
        if order is None:
            abort(404, message=f"Order {order_id} not found")
        return order.to_dict(), 200
