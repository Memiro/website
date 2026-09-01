from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class LegalConfig:
    """Configuration of the legal texts a stored inquiry is evidence against."""

    # No default: the revision travels with every inquiry as proof of what the
    # visitor accepted, and a deployment that forgot to name it has to say so
    # at start, not store the wrong proof quietly (ADR-0006).
    consent_version: str
