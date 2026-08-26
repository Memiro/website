from dishka import Provider, Scope


class InteractorProvider(Provider):
    """One explicit ``provide_all(...)`` list of interactors (§9.3).

    Empty until the first use case lands; the walking-skeleton slice adds
    the first entry.
    """

    scope = Scope.REQUEST
