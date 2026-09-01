import pytest

from memiro.entities.errors.inquiry import ConsentRequiredError
from memiro.entities.inquiry.consent import Consent, given_consent


def test_a_ticked_consent_carries_the_revision_the_visitor_accepted() -> None:
    """Consent is the revision of the text, not a flag beside it."""
    assert given_consent(given=True, version="2026-08-31") == Consent(version="2026-08-31")


def test_a_consent_naming_no_revision_is_a_defect() -> None:
    """A consent without the revision proves nothing, and an unnamed one is a deployment defect."""
    with pytest.raises(RuntimeError, match="must name the revision"):
        given_consent(given=True, version="")


def test_an_unticked_consent_is_refused() -> None:
    """Without the visitor's tick there is no consent to build an inquiry from."""
    with pytest.raises(ConsentRequiredError, match="Consent is required"):
        given_consent(given=False, version="2026-08-31")
