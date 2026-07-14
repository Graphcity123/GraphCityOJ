# GCOJ — 在线评测系统

前后端分离的 Online Judge 系统。

## 架构

```
浏览器 → Django 前端 (8501) → HTTP → FastAPI 后端 (8000) → SQLite + 题目文件
```

- **后端**: FastAPI + async SQLAlchemy + aiosqlite + psutil 评测引擎
- **前端**: Django 模板渲染 + requests HTTP 客户端

## 快速开始

```bash
# 后端
cd backend
pip install -e .
uvicorn app.main:app --reload --port 8000 --reload-exclude 'work/*'

# 前端（另一个终端）
cd frontend
python3 manage.py runserver 8501
```

- 后端: http://localhost:8000/health
- 前端: http://localhost:8501

## 默认管理员

- 用户名: admin
- 密码: admintestpassword

## 功能

- 用户注册/登录/角色管理
- 题目浏览与 Markdown 渲染
- 代码提交与异步评测（Python/C++）
- 评测结果实时查看（时间/内存/测试点详情）
- 管理员：重置系统、导入导出、用户管理、上传题目
- 频率限制：3 次/分钟/用户
- 数据持久化：SQLite 存储 + 题目磁盘文件
