# OJ System

实验二：在线评测系统 —— 构建一个小型但功能完整的 Online Judge 系统。

## 技术栈

- **Web 框架**: FastAPI (async/await)
- **认证**: Starlette SessionMiddleware
- **数据存储**: 内存字典（现阶段），计划迁移至 SQLite
- **密码**: SHA-256 加盐哈希
- **评测引擎**: asyncio + subprocess，支持资源限制
- **前端**: Streamlit（Python）

## 快速开始

`ash
cd oj-system

# 安装依赖
pip install -e .

# 启动服务
uvicorn app.main:app --reload --port 8000
`

启动后访问 http://localhost:8000/health 验证服务。

# 启动前端（另一个终端）
streamlit run frontend/app.py --server.port 8501

前端访问 http://localhost:8501。

## 实现进度

| Step | 状态 | 说明 |
|------|------|------|
| Step1：题目管理 | ✅ 已完成 | 题目增删查改，分页列表，管理员删除 |
| Step2：题目评测 | ✅ 已完成 | Python/C++ 评测，动态注册语言，时间/内存限制 |
| Step3：评测列表 | ✅ 已完成 | 评测历史、详情、重新评测 |
| Step4：用户管理 | ✅ 已完成 | 注册、登录、角色管理 |
| Step5：日志与权限 | ✅ 已完成 | 日志查询、审计、测例公开控制 |
| Step6：持久化存储 | ✅ 已完成 | SQLite 迁移、数据导出/导入 |
| Adv2：前端交互 | ✅ 已完成 | Streamlit 前端：登录、提交、评测结果查询 |

## 项目结构

`
oj-system/
├── app/
│   ├── main.py              # FastAPI 入口，中间件与路由注册
│   ├── config.py            # pydantic-settings 配置
│   ├── storage.py           # 内存存储层（dict 抽象，预留 SQLite 迁移）
│   ├── schemas.py           # 全部 Pydantic 数据模型与枚举
│   ├── api/
│   │   ├── auth.py          # Step4: 登录/登出
│   │   ├── problems.py      # Step1: 题目 CRUD
│   │   ├── judge.py         # Step2: 语言管理
│   │   ├── submissions.py   # Step2+3: 评测提交/列表/详情/重评
│   │   ├── users.py         # Step4: 注册/信息/角色变更/创建管理员
│   │   ├── logs.py          # Step5: 日志查询/权限/审计
│   │   └── admin.py         # Step6: 重置/导出/导入
│   ├── utils/
│   │   ├── auth.py          # Session 认证与权限校验
│   │   ├── exceptions.py    # HTTP 异常类
│   │   ├── judge_engine.py  # 异步评测引擎（subprocess）
│   │   └── rate_limiter.py  # 请求频率限制（429）
│   ├── models/              # SQLAlchemy ORM 模型
│   │   ├── user.py
│   │   ├── problem.py
│   │   ├── submission.py
│   │   └── log.py
│   ├── db/                  # 数据库引擎与迁移
│   │   ├── database.py
│   │   └── models.py
│   ├── core/                # 核心逻辑（预留）
│   └── services/            # 业务服务（预留）
├── frontend/               # Streamlit 前端
│   ├── app.py              # 主应用
│   └── api.py              # API 客户端
├── problems/                # 题目配置目录（TOML/JSON）
│   └── example/             # 示例题目：A+B Problem
├── tests/                   # pytest 测试用例
├── test_api.http            # VS Code REST Client 测试文件
├── pyproject.toml           # 项目配置与依赖
└── README.md
`

## API 接口总览

接口详情以 [api.md](https://keg-course.github.io/python-docs/oj/api/) 为准，以下为快速参考。

### Step1 题目管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/problems/ | 题目列表（分页） |
| POST | /api/problems/ | 创建题目 |
| GET | /api/problems/{id} | 题目详情 |
| DELETE | /api/problems/{id} | 删除题目（管理员） |

### Step2 评测控制

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/languages/ | 支持的语言列表 |
| POST | /api/languages/ | 注册新语言 |

### Step3 评测列表

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/submissions/ | 提交代码评测（异步，返回 pending） |
| GET | /api/submissions/ | 评测列表（分页、筛选，需提供 problem_id 或 user_id） |
| GET | /api/submissions/{id} | 评测详情（本人/管理员） |
| PUT | /api/submissions/{id}/rejudge | 重新评测（管理员） |
| GET | /api/submissions/{id}/log | 查询评测日志 |

### Step4 用户管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/users/ | 用户注册 |
| POST | /api/auth/login | 用户登录 |
| POST | /api/auth/logout | 用户登出 |
| GET | /api/users/ | 用户列表（管理员） |
| GET | /api/users/{user_id} | 用户信息（本人/管理员） |
| PUT | /api/users/{user_id}/role | 修改角色（管理员） |
| POST | /api/users/admin | 创建管理员账户 |

### Step5 日志与权限

| 方法 | 路径 | 说明 |
|------|------|------|
| PUT | /api/problems/{problem_id}/log_visibility | 配置测例公开状态 |
| GET | /api/logs/access/ | 审计日志（管理员） |

### Step6 数据持久化

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/reset/ | 系统重置（管理员） |
| GET | /api/export/ | 数据导出（管理员） |
| POST | /api/import/ | 数据导入（管理员） |

## 默认管理员账号

- 用户名：dmin
- 密码：dmintestpassword
- 执行 POST /api/reset/ 后自动创建，也可通过 POST /api/users/admin 新建管理员

## 注意事项

- 评测提交通过 BackgroundTasks 异步执行，返回 {"status": "pending"}，随后可通过 GET /api/submissions/{id} 查询结果
- 同一用户每分钟最多提交 3 次评测（超限返回 HTTP 429）
- 所有错误响应统一格式：{"code": <http状态码>, "msg": "<错误描述>", "data": null}
- 异常处理顺序：401 > 403 > 400 > 429 > 409 > 404 > 500

## 本地测试

### 方式一：VS Code REST Client

安装 REST Client 插件，打开项目根目录的 	est_api.http，点击每个请求上方的 Send Request 即可发送。

### 方式二：命令行 curl

`ash
# 健康检查
curl http://localhost:8000/health

# 系统重置
curl -X POST http://localhost:8000/api/reset/

# 注册
curl -X POST http://localhost:8000/api/users/ \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test123456"}'

# 登录
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admintestpassword"}' \
  -c cookies.txt

# 携带 Cookie 的后续请求
curl -b cookies.txt http://localhost:8000/api/problems/
`

### 方式三：Streamlit 前端

启动后端后，另开终端：

`ash
cd oj-system
streamlit run frontend/app.py --server.port 8501
`

浏览器打开 http://localhost:8501，登录后即可使用。

## 实验要求

请参考 [实验说明](https://keg-course.github.io/python-docs/oj/)。
