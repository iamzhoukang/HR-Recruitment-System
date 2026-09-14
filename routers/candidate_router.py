import os.path
import uuid

from exceptiongroup import catch
from fastapi import APIRouter, Depends, HTTPException, UploadFile , File
from openai.resources.containers.files import content
from sqlalchemy.sql.functions import current_user
from schemas.candidate_schema import ResumeUploadRespSchema
from repository.candidate_repo import ResumeRepo
from dependencies import get_session_instance , get_current_user
from settings import settings
from fastapi import status
from models import AsyncSession
from models.user import UserModel
from core.pdf import WordToPdfConverter
from loguru import logger
import aiofiles

router = APIRouter(prefix="/candidate",tags=["candidate"])

#上传简历
@router.post("/resume/upload",summary="上传简历",response_model=ResumeUploadRespSchema)
async def resume_upload(
        file : UploadFile = File(...),
        session : AsyncSession  = Depends(get_session_instance),
        current_user : UserModel = Depends(get_current_user),
):
    #校验文件类型
    # 简历：图片，pdf,word
    allowed_mime_types = [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "image/jpeg",
        "image/png",
        "image/jpg",
    ]
    if file.content_type not in allowed_mime_types:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="该文件不支持")

    #保存文件
    #如果是word文档要转换成pdf后识别
    resume_dir = settings.RESUME_DIR
    file_extension = os.path.splitext(file.filename)[-1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(resume_dir, unique_filename)
    try:
        async with aiofiles.open(file_path, mode="wb") as fp:
            content = await file.read(1024)
            while content:
                await fp.write(content)
                content = await file.read(1024)
    finally:
        await file.close()

    #如果是word就转换成pdf
    if file_extension == ".docx" or file_extension == ".doc":
        pdf_path = file_path.replace(file_extension,".pdf")
        converter = WordToPdfConverter(
            word_path=file_path,
            output_pdf_path=pdf_path,
        )
        try:
            await converter.convert()
            file_path = pdf_path
        except Exception as e:
            logger.error(f"word转pdf失败:{e}")

    #将简历数据存储到数据库中
    async with session.begin():
        resume_repo = ResumeRepo(session)
        resume = await resume_repo.create_resume(file_path=file_path,uploader_id=current_user.id)
    return {"resume":resume}

