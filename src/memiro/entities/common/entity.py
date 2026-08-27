from abc import ABC


class Entity(ABC):  # noqa: B024  # a marker base by design: it declares a role, not behaviour
    """Marker base class for domain entities."""
