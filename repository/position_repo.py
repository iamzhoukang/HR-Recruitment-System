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