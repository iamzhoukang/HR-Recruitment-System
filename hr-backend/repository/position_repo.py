from models import positions
from models.positions import PositionModel
from sqlalchemy import select, delete

from . import BaseRepo
from models.user import UserModel, DingdingUserModel, DepartmentModel
from typing import Sequence, List
from sqlalchemy.orm import selectinload

class PositionRepo(BaseRepo):
    async def create_position(self, position_data: dict) -> PositionModel:
        position = PositionModel(**position_data)
        self.session.add(position)
        return position

    async def get_possition_list(self,
                                 user:UserModel,
                                 page: int = 1,
                                 size: int = 10,
                                )->Sequence[PositionModel]:
        stmt = select(PositionModel)
        #如果是HR只返回该HR负责的职位，如果是其它部分的成员，那么返回该员工所在，如果是superuser没有约束
        if user.is_hr and (not user.is_superuser):
            department_ids = [d.id for d in user.managed_departments]
            stmt = stmt.where(PositionModel.department_id.in_(department_ids))
        elif (not user.is_hr) and (not user.is_superuser):
            stmt = stmt.where(PositionModel.department_id == user.department_id)
        #分页
        limit = size
        offset = (page - 1) * size
        stmt = stmt.limit(limit).offset(offset).order_by(PositionModel.created_at.desc())
        positions = (await self.session.scalars(stmt)).all()
        return positions

    async def get_by_id(self, position_id: str) -> PositionModel | None:
        stmt = select(PositionModel).where(PositionModel.id == position_id)
        position = await self.session.scalar(stmt)
        return position

    async def delete_position(self, position_id: str):
        stmt = delete(PositionModel).where(PositionModel.id == position_id)
        await self.session.execute(stmt)