# HR Recruitment System

AI 智能招聘系统，采用前后端分离的 monorepo 结构。

## 目录结构

```text
HR-Recruitment-System/
├── hr-backend/   # FastAPI、PostgreSQL、Redis、LangChain/LangGraph Agent
└── hr-frontend/  # Vue 3、TypeScript、Vite、Pinia、Vue Router、Tailwind CSS
```

## 启动后端

```bash
cd hr-backend
uv sync
uv run uvicorn main:app --reload
```

后端依赖数据库、Redis、邮件、钉钉及模型等环境变量。不要将本地 `.env` 或密钥提交到仓库。

## 启动前端

```bash
cd hr-frontend
npm install
npm run dev
```

## 开发约定

- Python 虚拟环境、Node.js 依赖、构建产物和运行时上传文件不进入 Git。
- 后端和前端分别维护自己的依赖清单。
- 涉及接口变更时，建议在同一次提交中同步修改前后端。
