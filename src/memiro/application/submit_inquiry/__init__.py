"""Use case: Submit an inquiry.

Actor: the customer (anonymous).

Two scenarios: the preview of a selection, which stores nothing, and the
submission, which stores the same positions and answers with the same
projection of them.
"""

from memiro.application.submit_inquiry.config import LegalConfig
from memiro.application.submit_inquiry.preview_inquiry import InquiryPreview, PreviewInquiry, PreviewInquiryForm
from memiro.application.submit_inquiry.shared import (
    InquiryItemForm,
    PreviewedConfiguration,
    PreviewedItem,
    PreviewedValue,
)
from memiro.application.submit_inquiry.submit_inquiry import CreatedInquiry, SubmitInquiry, SubmitInquiryForm
from memiro.entities.inquiry.entity import InquirySource

__all__ = [
    "CreatedInquiry",
    "InquiryItemForm",
    "InquiryPreview",
    "InquirySource",
    "LegalConfig",
    "PreviewInquiry",
    "PreviewInquiryForm",
    "PreviewedConfiguration",
    "PreviewedItem",
    "PreviewedValue",
    "SubmitInquiry",
    "SubmitInquiryForm",
]
