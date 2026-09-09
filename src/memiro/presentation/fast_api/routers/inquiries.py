from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from memiro.application.submit_inquiry import (
    CreatedInquiry,
    InquiryPreview,
    PreviewInquiry,
    PreviewInquiryForm,
    SubmitInquiry,
    SubmitInquiryForm,
)

router = APIRouter(tags=["inquiries"], route_class=DishkaRoute, prefix="/inquiries")


@router.post("")
async def submit_inquiry(
    interactor: FromDishka[SubmitInquiry],
    data: SubmitInquiryForm,
) -> CreatedInquiry:
    """HTTP endpoint for submitting one visitor inquiry."""
    return await interactor.execute(data)


@router.post("/preview")
async def preview_inquiry(
    interactor: FromDishka[PreviewInquiry],
    data: PreviewInquiryForm,
) -> InquiryPreview:
    """HTTP endpoint for showing a selection the way a submission would store it."""
    return await interactor.execute(data)
