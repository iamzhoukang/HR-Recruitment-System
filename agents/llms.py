import os
from langchain_openai import ChatOpenAI

deepseek_key = os.getenv("DEEPSEEK_API_KEY")
qwen_key = os.getenv("DASHSCOPE_API_KEY")

qwen_llm = ChatOpenAI(
    model="qwen3-max",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key=qwen_key,
)

deepseek_llm = ChatOpenAI(
    model="deepseek-v4-flash",
    base_url="https://api.deepseek.com",
    api_key=deepseek_key,
)