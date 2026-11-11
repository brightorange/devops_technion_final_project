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


def _check_name(value):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 120:
        return None, "must be a non-empty string of at most 120 characters"
    return value.strip(), None


def _check_description(value):
    if not isinstance(value, str):
        return None, "must be a string"
    return value, None


def _check_price(value):
    price = to_price(value)
    if price is None:
        return None, "must be a number greater than 0 with at most 2 decimals"
    return price, None


def _check_stock(value):
    if not is_int(value) or value < 0:
        return None, "must be a non-negative integer"
    return value, None


# field name -> (validator, required when creating)
PRODUCT_FIELDS = {
    "name": (_check_name, True),
    "description": (_check_description, False),
    "price": (_check_price, True),
    "stock": (_check_stock, False),
}


def parse_product(data, partial=False):
    """Validate product fields. partial=True (used by PUT) allows missing fields."""
    fields, errors = {}, {}

    for key, (check, required) in PRODUCT_FIELDS.items():
        # A field is validated when it is present, and additionally when it is
        # required and this is a create rather than a partial update.
        if key not in data and (partial or not required):
            continue
        value, error = check(data.get(key))
        if error:
            errors[key] = error
        else:
            fields[key] = value

    if partial and not fields and not errors:
        errors["body"] = "no updatable fields provided"

    return fields, errors
