import math
from decimal import Decimal

from flask import request
from flask_restful import abort

MAX_PRICE = Decimal("99999999.99")  # fits Numeric(10, 2)


def is_int(value):
    # bool is a subclass of int in Python, so True would otherwise pass as 1.
    return isinstance(value, int) and not isinstance(value, bool)


def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, message="Request body must be a JSON object")
    return data


def fail_if(errors):
    if errors:
        abort(400, message="Validation failed", errors=errors)


def positive_int(data, field, errors):
    value = data.get(field)
    if not is_int(value) or value < 1:
        errors[field] = "must be a positive integer"
    return value


def to_price(value):
    # Python's JSON parser accepts NaN/Infinity, so reject non-finite floats.
    if is_int(value) or (isinstance(value, float) and math.isfinite(value)):
        # Go through str() so 19.99 becomes Decimal("19.99"), not 19.98999...
        price = Decimal(str(value))
        if 0 < price <= MAX_PRICE and price.as_tuple().exponent >= -2:
            return price
    return None


def parse_product(data, partial=False):
    """Validate product fields. partial=True (used by PUT) allows missing fields."""
    fields, errors = {}, {}

    if "name" in data or not partial:
        name = data.get("name")
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
            errors["name"] = "must be a non-empty string of at most 120 characters"
        else:
            fields["name"] = name.strip()

    if "description" in data:
        if not isinstance(data["description"], str):
            errors["description"] = "must be a string"
        else:
            fields["description"] = data["description"]

    if "price" in data or not partial:
        price = to_price(data.get("price"))
        if price is None:
            errors["price"] = "must be a number greater than 0 with at most 2 decimals"
        else:
            fields["price"] = price

    if "stock" in data:
        stock = data["stock"]
        if not is_int(stock) or stock < 0:
            errors["stock"] = "must be a non-negative integer"
        else:
            fields["stock"] = stock

    if partial and not fields and not errors:
        errors["body"] = "no updatable fields provided"

    return fields, errors
