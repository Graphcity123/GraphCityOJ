# OJ System

实验二：在线评测系统 —— 构建一个小型但功能完整的 Online Judge 系统。

## 技术栈

- **框架**: FastAPI (async/await)
- **语言**: Python >= 3.11
- **数据库**: SQLite (via SQLAlchemy + aiosqlite)

## 快速开始

```bash
# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -e .

# 启动服务
uvicorn app.main:app --reload --port 8000
```

## 项目结构

参见文件树设计文档。

## 实验要求

请参考 [实验说明](https://keg-course.github.io/python-docs/oj/)。

### 基础模块 (共 30 分)

| Step | 名称 | 说明 |
|------|------|------|
| Step1 | 题目管理 | 配置解析、字段校验、异常处理 |
| Step2 | 评测控制 | 程序执行、资源限制、输出比对 |
| Step3 | 用户系统 | 注册/更新、权限管理 |
| Step4 | 任务状态管理 | 评测任务流转、调度 |
| Step5 | 评测日志 | 结构化日志记录与查询 |
| Step6 | 数据持久化 | 数据库存储、备份恢复 |

### 进阶模块 (选做，最多 +10 分)

| Adv | 名称 | 说明 |
|-----|------|------|
| Adv1 | Special Judge | 特殊题目评测 |
| Adv2 | 前端交互 | Streamlit 极简前端 |
| Adv3 | 安全机制 | Docker 容器控制 |
| Adv4 | 代码查重 | 剽窃检测 |
