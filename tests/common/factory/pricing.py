"""Model factories of the pricing use case — for the tests the values are indifferent to.

A test that is about the numbers builds its request by hand out of the demo
dictionary (`catalog.py`); a test that only needs *some* well-formed choices
takes them from here (§14.7.1).
"""

from polyfactory.factories.pydantic_factory import ModelFactory

from memiro.application.calculate_price import Selection


class SelectionFactory(ModelFactory[Selection]):
    """Build a syntactically valid choice pointing at nothing in particular."""

    __model__ = Selection
