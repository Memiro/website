from dataclasses import dataclass

from memiro.entities.errors.inquiry import ConsentRequiredError


@dataclass(frozen=True, slots=True)
class Consent:
    """The visitor's permission to process personal data, with the revision they accepted."""

    version: str

    def __post_init__(self) -> None:
        """Refuse a consent that names no revision: it would prove nothing (ADR-0006)."""
        if not self.version:
            msg = "Consent must name the revision the visitor accepted"
            raise RuntimeError(msg)


def given_consent(*, given: bool, version: str) -> Consent:
    """Turn the visitor's tick into consent, refusing the inquiry that carries none."""
    if not given:
        raise ConsentRequiredError
    return Consent(version=version)
