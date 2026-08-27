from dishka import Provider, Scope, provide_all

from memiro.application.calculate_price import CalculatePrice


class InteractorProvider(Provider):
    """One explicit ``provide_all(...)`` list of interactors (§9.3)."""

    scope = Scope.REQUEST

    interactors = provide_all(CalculatePrice)
