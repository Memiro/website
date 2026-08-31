from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from memiro.application.submit_inquiry import CreatedInquiry, SubmitInquiry, SubmitInquiryForm

router = APIRouter(tags=["inquiries"], route_class=DishkaRoute, prefix="/inquiries")


@router.post("")
async def submit_inquiry(
    interactor: FromDishka[SubmitInquiry],
    data: SubmitInquiryForm,
) -> CreatedInquiry:
    """HTTP endpoint for submitting one visitor inquiry."""
    return await interactor.execute(data)
