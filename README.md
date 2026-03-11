# Team BBS (FastAPI + JSON)

一个尽可能简单的论坛后端示例，基于 FastAPI + SQLAlchemy。
默认使用 SQLite，也支持 PostgreSQL。

## 功能

- 用户注册、登录、查询当前用户
- 板块创建与查询
- 帖子发布、编辑、删除、分页浏览
- 关键词搜索（标题、正文、标签）
- 一级回帖（回复）发布、编辑、删除、分页浏览
- 帖子收藏与取消收藏（按 `user_id`）
- 板块收藏与取消收藏（按 `user_id`）
- 默认行为：自动收藏自己创建的板块、自己发布的帖子、自己回复过的帖子

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
- `DATABASE_URL`（可选，默认 SQLite；可切换 PostgreSQL）
- `NOTIFY_TASK_ENABLED`（默认 `true`，是否开启未读提醒后台任务）
- `NOTIFY_TASK_INTERVAL_SECONDS`（默认 `30`，未读提醒扫描间隔）
- `NOTIFY_TASK_REQUEST_TIMEOUT_SECONDS`（默认 `2`，单次提醒请求超时）

后台提醒任务说明：

- 任务会周期性扫描存在未读通知的用户
- 并发异步发送请求到 `http://{username}:8000/notify`
- 请求体格式为：`{"message": {"content": "你有 N 条未读消息"}}`
- 采用 best-effort 策略，不处理返回结果

站内通知类型说明：

- `post_updated`：关注的帖子被作者编辑
- `new_reply`：关注的帖子有新回复
- `board_created`：有新板块创建（广播给其他用户）
- `new_post_in_board`：关注的板块下有新帖子（排除发帖人，5 分钟窗口去重）

启动后访问：

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

## Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

默认会同时启动 PostgreSQL，并通过 `DATABASE_URL` 连接。
如需本地 SQLite，可不设置 `DATABASE_URL`，应用会回退到 `sqlite:///./data/team_bbs.db`。

## 数据

- 默认 SQLite 数据库文件路径：`data/team_bbs.db`
- 支持通过 `DATABASE_URL` 切换到 PostgreSQL。

## 安全说明

- 为了保持最简实现，密码采用明文存储，token 也仅为本地简单会话标识。
- 请勿将该实现直接用于生产环境。
