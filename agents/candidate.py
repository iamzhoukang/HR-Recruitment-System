from langchain.agents import create_agent
from schemas.candidate_schema import CandidateSchema
from schemas.position_schema import PositionSchema
from schemas.user_schema import UserSchema
from langgraph.graph.message import BaseMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain.agents.middleware import ModelFallbackMiddleware,SummarizationMiddleware
from .llms import qwen_llm,deepseek_llm
from .prompts import CANDIDATE_PROCESS_SYSTEM_PROMPT
from settings import settings
from pydantic import BaseModel
from typing import Annotated, List,TypeVar,Optional
from langgraph.graph.message import add_messages

T = TypeVar("T")

def assign_state_property(left:T,right:Optional[T]):
    return right if right is not None else left

#checkpointer会自动保存state中的数据到数据库中
class CandidateAgentState(BaseModel):
    message:  Annotated[List[BaseMessage],add_messages]
    candidate : Annotated[CandidateSchema,assign_state_property]
    position: Annotated[PositionSchema,assign_state_property]
    interviewer: Annotated[UserSchema,assign_state_property]

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

    async def ainvoke(self,messgaes:list[BaseMessage],thread_id: str):
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
            tools=[],
            checkpointer= self.checkpointer,
        )
        response = await agent.invoke({
            "message": messgaes,
        }, {"thread_id": thread_id})


        return response

    async def __aenter__(self):
        self._checkpointer_conn = AsyncPostgresSaver.from_conn_string(settings.DATABASE_AGENT_URL)
        self._checkpointer = await self._checkpointer_conn.__aenter__()
        await self.checkpointer.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._checkpointer_conn.__aexit__(exc_type, exc_val, exc_tb)


    # async with CandidateProcessAgent(candidate,position,interviewer) as agent:
    #     await agent.ainvoke()