import string

from  settings import settings
from fastapi import APIRouter, Depends, BackgroundTasks
from schemas import ResponseSchema
from core.cache import HRCache , InviteInfoSchema ,DingTAlkTokenInfoSchema
from core.dingtalk import DingTalkApi
from schemas.user_schema import (
    UserLoginSchema,
    UserLoginResponseSchema,
    UserInviteSchema,
    UserRegisterSchema,
    UserListResponseSchema,
    UserStatusUpdateSchema,
    DepartmentResSchema,
)
from dependencies import (
    get_session_instance,
    get_auth_handler,
    AuthHandler,
    get_cache_instance,
    get_super_user,
    get_current_user,
 )
from models import AsyncSession
from repository.user_repo import UserRepo, DepartmentRepo
from models.user import UserModel, UserStatus
from fastapi.exceptions import HTTPException
from fastapi import status

from tasks import send_invite_email_task
from urllib.parse import urlencode,urljoin
from fastapi.templating import Jinja2Templates
from fastapi import Request
from fastapi.responses import RedirectResponse
import httpx
import random

jinja2Engine = Jinja2Templates(directory="templates")
#/docs
router = APIRouter(prefix="/user", tags=["user"])

@router.post("/login",summary="登陆",response_model=UserLoginResponseSchema)
async def login(
    login_data: UserLoginSchema,
    session: AsyncSession = Depends(get_session_instance),
    auth_handler:AuthHandler = Depends(get_auth_handler),
):
    #开启事务
    async with session.begin():
        #1,获取用户
        user_repo = UserRepo(session)
        user: UserModel = await user_repo.get_by_email(str(login_data.email))
        if not user:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,detail="该用户不存在")
        #2,验证密码是否准确
        if not user.check_password(login_data.password):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="邮箱或密码错误")
        #3，判断员工状态
        if user.status != UserStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="该员工状态不可用，请联系管理员")
        #4,生成JWToken
        tokens = auth_handler.encode_login_token(user.id)
        return {
            "access_token":tokens['access_token'],
            "refresh_token":tokens['refresh_token'],
            "user":user
        }

@router.post("/invite",summary="邀请用户,给指定邮箱发送邮件",response_model=ResponseSchema)
async def invite(
        invite_data: UserInviteSchema,
        background_tasks: BackgroundTasks,
        session: AsyncSession = Depends(get_session_instance),
        cache:HRCache = Depends(get_cache_instance),
        _:UserModel = Depends(get_super_user),
):
    email = invite_data.email
    department_id = invite_data.department_id
    async with session.begin():
        #先校验邮箱在数据库中是否存在
        user_repo = UserRepo(session)
        user: UserModel = await user_repo.get_by_email(str(email))
        if user:
            raise HTTPException(status_code= status.HTTP_400_BAD_REQUEST,detail="该邮箱已经注册")
        #校验department_id在数据库是否存在
        department_repo = DepartmentRepo(session)
        department = await department_repo.get_by_id(str(department_id))
        if not department:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="该部门不存在")
        #生成邀请码
        invite_code = "".join(random.sample(string.digits,6))
        #将邀请信息保存到缓存中
        await cache.set_invite_info(InviteInfoSchema(email=email,department_id=department_id,invite_code=invite_code))
        #发送给指定邮箱(后台执行)
        # await send_invite_email_task(email,invite_code)
        background_tasks.add_task(
            send_invite_email_task,
            email=str(email),
            invite_code=invite_code,
        )
        return ResponseSchema()

@router.post("/register",summary="注册")
async def register(
    register_data: UserRegisterSchema,
    session: AsyncSession = Depends(get_session_instance),
    cache:HRCache = Depends(get_cache_instance),
):
    email = register_data.email
    #校验邮箱和邀请码
    invite_info : InviteInfoSchema = await cache.get_invite_info(str(email))
    if not invite_info:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="注册邮箱不存在")
    if invite_info.invite_code != register_data.invite_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邀请码错误")

    #进行注册
    async with session.begin():
        #校验邮箱是否注册
        user_repo = UserRepo(session)
        user: UserModel = await user_repo.get_by_email(str(email))
        if user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="该邮箱已经被注册")
        #创建用户
        await user_repo.create_user({
            "email":email,
            "username": register_data.username,
            "realname":register_data.realname,
            "password":register_data.password,
            "department_id":invite_info.department_id,
        })
        return ResponseSchema()

@router.get(path="/list",summary="获取员工列表",response_model=UserListResponseSchema)
async def user_list(
    page : int = 1,
    size : int = 10,
    department_id : str|None = None,
    _: UserModel = Depends(get_super_user),
    session: AsyncSession = Depends(get_session_instance),
):
    async with session.begin():
        user_repo = UserRepo(session)
        users = await user_repo.get_user_list(page=page,size=size,department_id=department_id)
    return {"users":users}


@router.patch(path="/status/update",summary="修改员工状态",response_model=ResponseSchema)
async def update_status(
        status_data: UserStatusUpdateSchema,
        session: AsyncSession = Depends(get_session_instance),
        _: UserModel = Depends(get_super_user),
):
    async with session.begin():
        user_repo = UserRepo(session)
        user:UserModel = await user_repo.get_by_id(status_data.user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="该员工不存在")
        if user.is_superuser:
            raise HTTPException(status_code=status.HTTP_400_FORBIDDEN,detail="不能修改超级用户")
        user.status = status_data.status
    return ResponseSchema()


@router.get(path="/department/list",summary="获取所以部分列表",response_model=DepartmentResSchema)
async def department_list(
        session: AsyncSession = Depends(get_session_instance),
        _: str = Depends(get_current_user),
):
    async with session.begin():
        department_repo = DepartmentRepo(session)
        departments = await department_repo.get_department_list()
        return {"departments":departments}


@router.get("/dingtalk/authorize",summary="获取登陆钉钉的url")
async def dingtalk_authorize(
        current_user: UserModel = Depends(get_current_user),
):
    #redirect_uri:必须是公网能访问的url
    params = {
        "redirect_uri": urljoin(settings.BACKEND_BASE_URL,"/user/dingtalk/callback"),
        "response_type": "code",
        "client_id": settings.DINGTALK_CLIENT_ID,
        "scope":"openid",
        "state":current_user.id,
        "prompt":"consent"
    }
    authorize_url = f"https://login.dingtalk.com/oauth2/auth?{urlencode(params)}"
    return {"authorize_url":authorize_url}

@router.get("/dingtalk/callback")
async def dingtalk_callback(
        state: str,
        code: str | None = None,
        authCode: str | None = None,
        session: AsyncSession = Depends(get_session_instance),
        cache:HRCache = Depends(get_cache_instance),
):
    user_id = state
    async with httpx.AsyncClient() as client:
        # 获取token
        token_resp = await client.post(
            url = DingTalkApi.build_access_token_url(),
            json={
                "clientId": settings.DINGTALK_CLIENT_ID,
                "clientSecret": settings.DINGTALK_CLIENT_SECRET,
                "code": authCode,
                "grantType": "authorization_code",
            }
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="钉钉token获取失败")
        token_data = token_resp.json()
        access_token = token_data["accessToken"]
        refresh_token = token_data["refreshToken"]
        #存储token
        await cache.set_dingtalk_info(DingTAlkTokenInfoSchema(
            access_token=access_token,
            refresh_token=refresh_token,
            user_id= user_id
        ))
        #利用token获取用户信息
        my_info_resp = await client.get(
            url = DingTalkApi.build_get_my_info_url(),
            headers = {
                "x-acs-dingtalk-access-token": access_token,
            }
        )
        if my_info_resp.status_code != 200:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="钉钉个人信息获取失败")
        my_info = my_info_resp.json()
        nick = my_info["nick"]
        mobile = my_info["mobile"]
        openid = my_info["openId"]
        union_id = my_info["unionId"]
        #保存钉钉上用户的信息到数据库
        async with session.begin():
            user_repo = UserRepo(session)
            await user_repo.set_dingding_user(
                user_id=user_id,
                dingding_user_data= {
                    "nick": nick,
                    "mobile": mobile,
                    "open_id": openid,
                    "union_id": union_id
                }
            )
        #跳转到成功的页面
        return RedirectResponse(url=f"/user/dingtalk/authorize/success?nick={nick}")



@router.get("/dingtalk/authorize/success")
async def dingtalk_authorize_success(
        nick: str,
        request: Request,
):
    return jinja2Engine.TemplateResponse(
        request=request,
        name="ding_authorize_success.html",
        context={
            "username": nick,
        },
    )