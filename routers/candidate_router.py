import os.path
import uuid
from repository.user_repo import UserRepo
from core.cache import HRCache
from fastapi import APIRouter, Depends, HTTPException, UploadFile , File, BackgroundTasks
from repository.position_repo import PositionRepo
from schemas.candidate_schema import (
    ResumeUploadRespSchema,
    ResumePaseSchema,
    ResumeParseTaskRespSchema,
    ResumeParseTaskInfoRespSchema,
    CandidateCreateSchema
)
from repository.candidate_repo import ResumeRepo, CandidateRepo
from dependencies import get_session_instance, get_current_user, get_cache_instance
from settings import settings
from fastapi import status
from models import AsyncSession, interview
from models.user import UserModel
from core.pdf import WordToPdfConverter
from loguru import logger
from core.ocr import PaddleOcr
from tasks import ocr_parse_resume_task
from schemas import ResponseSchema
from tasks import run_candidate_agent
from schemas.candidate_schema import CandidateSchema
from schemas.position_schema import PositionSchema
from schemas.user_schema import UserSchema
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



#1用户发起一个简历识别的请求，创建一个后台任务，把任务id返回给前端
#2前端可以通过task_id来获取这个任务的执行结果,当执行结果为success时，就返回解析后的数据
@router.post("/resume/parse",summary="简历解析",response_model=ResumeParseTaskRespSchema)
async def parse_resume(
    resume_data: ResumePaseSchema,
    background_tasks: BackgroundTasks,
    _ : UserModel = Depends(get_current_user),
):
    #创建一个识别简历的后台任务
    task_id  = str(uuid.uuid4())
    background_tasks.add_task(ocr_parse_resume_task,resume_id = resume_data.resume_id,task_id = task_id)
    return {"task_id":task_id}

@router.get("/resume/parse/{task_id}",summary="获取任务状态",response_model=ResumeParseTaskInfoRespSchema)
async def get_task_status(
        task_id: str,
        cache:HRCache = Depends(get_cache_instance),
        _ : UserModel = Depends(get_current_user),
):
    task_info = await cache.get_task_info(task_id)
    return task_info.model_dump()

@router.post("/create",summary="创建候选人",response_model=ResponseSchema)
async def create_candidate(
    candidate_data: CandidateCreateSchema,
    session: AsyncSession = Depends(get_session_instance),
    current_user: UserModel = Depends(get_current_user),
):
    async with session.begin():
        candidate_dict = candidate_data.model_dump()
        candidate_dict['creator_id'] = current_user.id
        candidate_repo = CandidateRepo(session)
        candidate = await candidate_repo.create_candidate(candidate_dict)
    return ResponseSchema()

@router.get("/resume/ocr/test")
async def resume_ocr_test():
    file_path = os.path.join(settings.RESUME_DIR,"8cb83391-6844-463a-afac-8cd098f89649.pdf")
    paddle_ocr = PaddleOcr()
    job_id = await paddle_ocr.create_job(file_path)
    json_url = await paddle_ocr.poll_for_state(job_id)
    contents = await paddle_ocr.fetch_parsed_contents(json_url)
    logger.info(contents)
    return "success"


@router.get("/agent/test")
async def agent_test(
        background_tasks: BackgroundTasks,
        session: AsyncSession = Depends(get_session_instance),
):
    async with session.begin():
        candidate_repo = CandidateRepo(session)
        position_repo = PositionRepo(session)
        user_repo = UserRepo(session)

        candidate_model = await candidate_repo.get_by_id("5Awx5omuqZ7HyRfWosQKgW")
        position = await position_repo.get_by_id("JrUsgTqVj3qTGPRag3DaW8")
        interviewer = await user_repo.get_by_id("LP3ToeUstHVKKrweyxfhfC")

        background_tasks.add_task(
            run_candidate_agent,
            candidate = CandidateSchema.model_validate(candidate_model),
            position = PositionSchema.model_validate(position),
            interviewer = UserSchema.model_validate(interviewer),
        )

        return {"result":"success"}

