# GraphCity OJ — 在线评测系统

前后端分离的 Online Judge，支持 Python 和 C++ 代码评测。

## 架构

```
浏览器 → Django 前端 (:8501) → HTTP → FastAPI 后端 (:8000) → SQLite + 题目磁盘文件
                                              │
                                              ├── firejail 沙箱隔离
                                              ├── 并发评测 (4 线程)
                                              └── cgroup 内存精确统计
```

| 组件 | 技术栈 |
|------|--------|
| 后端 | FastAPI + async SQLAlchemy + aiosqlite |
| 前端 | Django 5 + 模板渲染 + requests |
| 沙箱 | firejail（cgroup 内存限制 + 网络隔离） |
| 评测 | 并发 asyncio.gather，4 线程并行 |
| 存储 | SQLite（元数据） + 磁盘文件（题目 / 测试点） |

## 快速开始

### 依赖

```bash
# WSL / Linux
sudo apt install firejail g++ python3-pip
```

### 后端

```bash
cd backend
pip install -e .
uvicorn app.main:app --reload --port 8000 --reload-exclude 'work/*'
```

### 前端

```bash
cd frontend
pip install django requests markdown pygments
python3 manage.py runserver 8501
```

- 后端 API：http://localhost:8000/health
- 前端界面：http://localhost:8501

## 默认管理员

| 用户名 | 密码 |
|--------|------|
| admin | admintestpassword |

## 功能

- **用户系统**：注册 / 登录 / 角色管理（admin / user / banned）
- **题目管理**：Markdown 题面渲染、文件上传创建、编辑元数据、增删测试点
- **代码评测**：Python / C++ 提交，firejail 沙箱隔离，并发 4 线程评测
- **评分模型**：每题总分 100，测试点均分
- **结果展示**：卡片网格（每行 8 个正方形）、颜色横幅、毫秒级时间显示
- **提交记录**：全部可见、筛选、整行点击跳转
- **管理员**：系统重置、数据导入导出、用户管理、题目上传编辑删除
- **频率限制**：普通用户 20 秒内最多 5 次提交，管理员无限制
- **主题系统**：4 套配色方案，CSS 自定义属性切换
- **字体**：HarmonyOS Sans SC（正文）+ JetBrains Mono（代码）
- **Markdown**：python-markdown + Pygments 代码高亮 + MathJax LaTeX
- **直角扁平设计**：参考 graphcity_blog 视觉风格

## 题目存储格式

```
problems/
├── 1/                  # A+B Problem
│   ├── problem.md      # 题面（YAML front-matter + Markdown）
│   ├── config.json     # 元数据（时间/内存/难度）
│   ├── 1.in / 1.out    # 测试点
│   └── ...
├── 2/                  # 下一个题目
└── ...
```

## 评测结果状态

| 状态 | 含义 | 颜色 |
|------|------|------|
| AC | Accepted | 绿 |
| WA | Wrong Answer | 红 |
| TLE | Time Limit Exceeded | 蓝 |
| MLE | Memory Limit Exceeded | 蓝 |
| RE | Runtime Error | 紫 |
| CE | Compile Error | 黄 |

## 测试

```bash
cd backend
PYTHONPATH=tests python3 -m pytest tests/ -v
```
