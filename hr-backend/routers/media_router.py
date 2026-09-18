from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from dependencies import get_current_user
from models.user import UserModel
from settings import settings


router = APIRouter(prefix="/media", tags=["media"])


@router.get("/{file_path:path}")
async def get_media_file(
    file_path: str,
    _: UserModel = Depends(get_current_user),
):
    resume_dir = Path(settings.RESUME_DIR).resolve()
    target = (resume_dir / file_path).resolve()

    # 防止通过 ../ 读取 upload 目录以外的文件。
    if target == resume_dir or resume_dir not in target.parents or not target.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在",
        )

    return FileResponse(target)
