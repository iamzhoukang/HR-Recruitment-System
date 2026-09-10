from datetime import timedelta
from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic import computed_field
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Settings(BaseSettings):
    # DB
    DB_USERNAME: str = "postgres"
    DB_PASSWORD: str = "770908"
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 5432
    DB_NAME: str = "hr_system"

    JWT_SECRET_KEY: str = "sfuehfhehieoisj"
    #access_token:一般2个小时过期
    #refresh_token:30天过期
    JWT_ACCESS_TOKEN_EXPIRES: timedelta = timedelta(days=365)
    JWT_REFRESH_TOKEN_EXPIRES: timedelta = timedelta(days=365)

    #redis配置
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379

    #邀请码过期时间
    INVITE_CODE_EXPIRE: int = 60*60*24*2 #两天


    #邮箱相关配置
    MAIL_USERNAME: str = Field(..., validation_alias="MAIL_USERNAME")
    MAIL_PASSWORD: str = Field(..., validation_alias="MAIL_PASSWORD")
    MAIL_FROM: str = Field(..., validation_alias="MAIL_USERNAME")
    MAIL_PORT: int = 465
    MAIL_SERVER: str = "smtp.qq.com"
    MAIL_FROM_NAME: str = "舟亢"
    MAIL_STARTTLS: bool = False
    MAIL_SSL_TLS: bool = True

    #钉钉相关的配置
    DINGTALK_CLIENT_ID: str = Field(...,validation_alias="DINGTALK_APP_KEY")
    DINGTALK_CLIENT_SECRET: str = Field(...,validation_alias="DINGTALK_APP_SECRET")

    #前端和后端的域名
    BACKEND_BASE_URL:str = "https://starboard-simile-provided.ngrok-free.dev"



    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+psycopg://{self.DB_USERNAME}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


settings = Settings()