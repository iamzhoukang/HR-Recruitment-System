from fastapi import APIRouter, Depends, HTTPException
from models.user import UserModel
from models import AsyncSession
from dependencies import get_current_user,get_session_instance
from repository import position_repo
from schemas.position_schema import PositionCreateSchema,PositionRespSchema
from repository.position_repo import PositionRepo
router = APIRouter(prefix="/position",tags=["Position"])

@router.post("/create",summary="创建职位",response_model=PositionRespSchema)
async def create_position(
        position_data : PositionCreateSchema,
        current_user: UserModel = Depends(get_current_user),
        session:AsyncSession  = Depends(get_session_instance),
):
    async with session.begin():
        position_repo = PositionRepo(session)
        position_dict = position_data.model_dump()
        position_dict['creator_id'] = current_user.id
        position_dict['department_id'] = current_user.department_id
        position = await position_repo.create_position(position_dict)
        return {"position": position}
