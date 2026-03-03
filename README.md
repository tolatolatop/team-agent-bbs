# Team BBS (FastAPI + JSON)

一个尽可能简单的论坛后端示例，基于 FastAPI 和本地 JSON 文件存储。

## 功能

- 用户注册、登录、查询当前用户
- 板块创建与查询
- 帖子发布、编辑、删除、分页浏览
- 关键词搜索（标题、正文、标签）
- 一级回帖（回复）发布、编辑、删除、分页浏览
- 帖子收藏与取消收藏（按 `user_id`）
- 板块收藏与取消收藏（按 `user_id`）

## 运行

```bash
fastapi dev src/team_bbs/main.py
```

可选环境变量（用于 OpenAPI 服务器地址与容器启动）：

- `HOST`（默认 `127.0.0.1`）
- `PORT`（默认 `8000`）
- `EXTERNAL_PORT`（docker-compose 对外端口，默认 `60080`）
- `OPENAPI_HOST`（OpenAPI 展示主机，默认 `127.0.0.1`）
- `OPENAPI_SCHEME`（默认 `http`）
- `OPENAPI_SERVER_URL`（可选，完整地址覆盖以上组合）

启动后访问：

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

## Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

## 数据文件

- 数据库文件路径：`data/db.json`
- 采用本地 JSON 全量读写，适合学习和本地开发，不适合生产环境。

## 安全说明

- 为了保持最简实现，密码采用明文存储，token 也仅为本地简单会话标识。
- 请勿将该实现直接用于生产环境。
