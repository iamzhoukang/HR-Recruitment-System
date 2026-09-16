from langchain.agents import create_agent
from models.user import DingdingUserModel
from schemas.candidate_schema import CandidateSchema
from schemas.position_schema import PositionSchema
from schemas.user_schema import UserSchema
from schemas.agent_schema import AgentCandidateScoreSchema
from langgraph.graph.message import BaseMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain.agents.middleware import ModelFallbackMiddleware,SummarizationMiddleware
from .llms import qwen_llm,deepseek_llm
from .prompts import CANDIDATE_PROCESS_SYSTEM_PROMPT,SCORE_FOR_CANDIDATE_SYSTEM_PROMPT,SCORE_FOR_CANDIDATE_USER_PROMPT
from settings import settings
from pydantic import BaseModel
from typing import Annotated, List,TypeVar,Optional
from langchain.tools import tool , ToolRuntime
from langgraph.graph.message import add_messages
from langchain_core.prompts import PromptTemplate
from models import AsyncSessionFactory
from repository.candidate_repo import CandidateAIScoreRepo,CandidateRepo
from models.candidate import CandidateStatusEnum
from repository.user_repo import UserRepo
from core.dingtalk import DingTalkHttp
from core.cache import HRCache
from loguru import logger
from core.cache import DingTAlkTokenInfoSchema
from datetime import datetime ,timedelta
from typing import Any
from utils.available_time import find_available_slot
from utils.iso8601 import datetime_to_iso8601_beijing,iso8601_to_datetime_beijing
from core.email_bot import EmailBot, EmailBotSettings, test
import json


async def get_dingtalk_access_token(user_id: str) -> str:
    dingding_http = DingTalkHttp()

    # 2. 从缓存中获取该用户的refresh_token
    cache: HRCache = HRCache()
    token_info = await cache.get_dingtalk_info(user_id)
    if not token_info:
        error_message = f"{user_id}用户钉钉授权已过期！"
        logger.error(error_message)
        raise ValueError(error_message)

    try:
        # 3. 根据refresh_token刷新access_token
        refresh_token, access_token = await dingding_http.refresh_access_token(token_info.refresh_token)

        # 4. 将获取到的token信息重新设置到缓存中
        await cache.set_dingtalk_info(
            DingTAlkTokenInfoSchema(
                user_id=user_id,
                access_token=access_token,
                refresh_token=refresh_token
            )
        )

        return access_token
    except Exception as e:
        logger.error(e)
        raise ValueError(e)




T = TypeVar("T")

def assign_state_property(left:T,right:Optional[T]):
    return right if right is not None else left

#checkpointer会自动保存state中的数据到数据库中
class CandidateAgentState(BaseModel):
    messages:  Annotated[List[BaseMessage],add_messages]
    candidate : Annotated[CandidateSchema,assign_state_property]
    position: Annotated[PositionSchema,assign_state_property]
    interviewer: Annotated[UserSchema,assign_state_property]

@tool()
async def score_for_candidate(
    runtime:ToolRuntime[CandidateAgentState],
):
    """
       根据职位信息，给职位上的候选人进行评分。
       评分结果会存入数据库中，并根据评分结果修改候选人状态。
       return：
       - str | None: 评分结果的JSON字符串，如果评分失败则返回None
    """
    candidate : CandidateSchema= runtime.state['candidate']
    position = runtime.state['position']

    score_agent = create_agent(
        model = qwen_llm,
        system_prompt=SCORE_FOR_CANDIDATE_SYSTEM_PROMPT,
        middleware=[
            ModelFallbackMiddleware(first_model=deepseek_llm),
        ],
        response_format=AgentCandidateScoreSchema,
    )
    user_prompt_template = PromptTemplate.from_template(SCORE_FOR_CANDIDATE_USER_PROMPT)
    user_prompt = user_prompt_template.invoke({
        "candidate": candidate.model_dump_json(),
        "position": position.model_dump_json(),
    })
    response = await score_agent.ainvoke({
        "messages": [{
            "role": "user",
            "content": user_prompt.text,
        }]
    })
    candidate_score: AgentCandidateScoreSchema = response['structured_response']

    # 将评分和候选人状态放在同一个事务中，任一步失败都会一起回滚。
    try:
        async with AsyncSessionFactory() as session:
            async with session.begin():
                score_repo = CandidateAIScoreRepo(session)
                candidate_repo = CandidateRepo(session)
                # 将得分插入到数据库里面
                await score_repo.create_candidate_score(
                    candidate_id=candidate.id,
                    candidate_score_dict=candidate_score.model_dump(),
                )
                # 判断得分情况，如果超过8分则通过AI筛选，否则筛选失败。
                status = CandidateStatusEnum.AI_FILTER_FAILED
                if candidate_score.overall_score > 8:
                    status = CandidateStatusEnum.AI_FILTER_PASSED

                await candidate_repo.update_candidate_status(
                    candidate_id=candidate.id,
                    status=status,
                )
    except Exception as e:
        logger.exception(e)
        return f"得分工具执行失败，错误信息为：{e}"
    return f"得分工具执行成功，该候选人得分：{candidate_score.model_dump_json()}"


@tool()
async def get_interviewer_available_slot(
        runtime:ToolRuntime[CandidateAgentState],
):
    """
       根据职位信息，获取面试官可用的面试时间。
       """
    interviewer:UserSchema = runtime.state['interviewer']
    #获取该用户的钉钉账号
    union_id: str | None = None
    try:
        async with AsyncSessionFactory() as session:
            async with session.begin():
                user_repo = UserRepo(session)
                dingding_user: DingdingUserModel | None = await user_repo.get_dingding_user(
                    user_id=interviewer.id
                )
                if not dingding_user:
                    return "获取面试官可用时间失败：没有绑定钉钉账号！"
                union_id = dingding_user.union_id
    except Exception as e:
        logger.exception(e)
        return f"获取面试官可用时间失败：{e}"

    try:
        # 获取access_token
        access_token: str = await get_dingtalk_access_token(interviewer.id)
    except Exception as e:
        logger.error(e)
        return f"获取面试官可用时间失败：{e} "

    #从钉钉上获取面试官的日程安排
    try:
        dingtalk_http = DingTalkHttp()
        tomorrow_nine = (datetime.now() + timedelta(days=1)).replace(
            hour=9,
            minute=0,
            second=0,
            microsecond=0,
        )
        events: list[dict[str, Any]] = await dingtalk_http.get_calendar_list(
            union_id=union_id,
            access_token=access_token,
            time_min=tomorrow_nine,
            time_max=tomorrow_nine + timedelta(days=7),
        ) or []
        # find_available_slot 内部使用无时区 datetime，所以这里统一移除时区信息。
        busy_slots = [
            (
                iso8601_to_datetime_beijing(
                    event['start']['dateTime']
                ).replace(tzinfo=None),
                iso8601_to_datetime_beijing(
                    event['end']['dateTime']
                ).replace(tzinfo=None),
            )
            for event in events
        ]
        available_slots: List[tuple[datetime, datetime]] = find_available_slot(
            busy_slots,
            start_date=tomorrow_nine,
        )
        if len(available_slots) == 0:
            return "获取面试官可用时间失败：7天内没有空闲时间！"
        available_times = [
            {
                "start": datetime_to_iso8601_beijing(slot[0]),
                "end": datetime_to_iso8601_beijing(slot[1]),
            }
            for slot in available_slots
        ]
        return f"找到面试官可用的时间：{json.dumps(available_times, ensure_ascii=False)}"
    except Exception as e:
        logger.exception(e)
        return f"获取面试官可用时间失败：{e}"

@tool()
async def send_interview_email(
        interview_datetime_str: str,
        runtime: ToolRuntime[CandidateAgentState],
):
    """
       给候选人发送面试时间邀请（并非最终面试时间，后续可能还需要通过邮件来和候选人协商最终面试时间）
       :param interview_datetime_str: 面试时间的字符串
       """
    candidate = runtime.state['candidate']
    position = runtime.state['position']
    email_bot_settings = EmailBotSettings(
        imap_host= settings.EMAIL_BOT_IMAP_HOST,
        smtp_host= settings.EMAIL_BOT_SMTP_HOST,
        email=settings.EMAIL_BOT_EMAIL,
        password=settings.EMAIL_BOT_PASSWORD,
    )
    async with EmailBot(email_bot_settings) as bot:
        subject = "面试邀请-协商面试时间"
        body = f"""
尊敬的{candidate.name}，
您好！
感谢您投递我司{position.title}职位。
我们初步确定了您的面试时间，请您确认是否方便。
面试时间：{interview_datetime_str}
请您确认是否方便，如果方便，请您回复“确认”。
 如果不方便，请回复您方便的时间，我们将会重新协商面试时间。
谢谢！
        """
        try:
            await bot.send_email(
                to = candidate.email,
                subject=subject,
                test = body,
            )
        except Exception as e:
            logger.error(e)
            return f"给候选人发送邮件失败：{e}"

        return f"给候选人发送面试邀请邮件成功！面试时间初步确定为：{interview_datetime_str}"



class CandidateProcessAgent:
    def __init__(self,
        candidate: CandidateSchema | None = None,
        position: PositionSchema | None = None,
        interviewer:UserSchema | None = None,
        ):
        self.candidate = candidate
        self.position = position
        self.interviewer = interviewer
        self._checkpointer = None

    async def ainvoke(self, messages: list[BaseMessage], thread_id: str):
        assert self._checkpointer is not None
        agent = create_agent(
            model=qwen_llm,
            system_prompt=CANDIDATE_PROCESS_SYSTEM_PROMPT,
            state_schema=CandidateAgentState,
            middleware=[
                ModelFallbackMiddleware(first_model=deepseek_llm),
                SummarizationMiddleware(
                    model=deepseek_llm,
                    trigger=("tokens", 100000),
                    keep=("tokens", 20000),
                ),
            ],
            tools=[score_for_candidate, get_interviewer_available_slot,send_interview_email],
            checkpointer=self._checkpointer,
        )
        response = await agent.ainvoke(
            {
                "messages": messages,
                "candidate": self.candidate,
                "position": self.position,
                "interviewer": self.interviewer,
            },
            {"configurable": {"thread_id": thread_id}},
        )


        return response

    async def __aenter__(self):
        self._checkpointer_conn = AsyncPostgresSaver.from_conn_string(settings.DATABASE_AGENT_URL)
        self._checkpointer = await self._checkpointer_conn.__aenter__()
        await self._checkpointer.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._checkpointer_conn.__aexit__(exc_type, exc_val, exc_tb)


    # async with CandidateProcessAgent(candidate,position,interviewer) as agent:
    #     await agent.ainvoke()
