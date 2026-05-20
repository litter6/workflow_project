# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目结构

本仓库包含两个独立子项目：

1. **Django 企业审批工作流系统**（根目录）
2. **电商 AI 聊天工具**（`ecommerce_ai_chat/` 目录）

**操作范围规则**：操作某个子项目时，只能修改该目录内的文件，绝不影响其他文件夹。

---

## 子项目一：Django 工作流系统

### 启动命令

```bash
# 激活 venv（Windows）
venv\Scripts\activate

# 数据库迁移
python manage.py migrate

# 启动开发服务器（端口 8000）
python manage.py runserver
```

### 架构概览

- **`workflow_system/`** — Django 项目配置，MySQL 数据库，`simpleui` admin 后台
- **`accounts/`** — 自定义 User 模型（继承 `AbstractUser`），四种角色：`销售人员`、`技术人员`、`老板`、`设计师`
- **`workflows/`** — 核心审批逻辑

审批流程模型链路：`ApprovalProcess` → `ApprovalProcessNode`（支持或签/会签）→ `ApprovalInstance` → `ApprovalRecord`

关联业务模型：`Project`（1:1 绑定 ApprovalInstance）、`Document`、`Notification`、`PriceItem`、`Quotation`、`QuotationItem`

状态机逻辑集中在 `workflows/services.py` 的 `ApprovalService`，提供 `approve`、`reject`、`countersign` 方法。

---

## 子项目二：电商 AI 聊天工具

### 启动命令

```bash
# 后端（在 ecommerce_ai_chat/backend/ 目录）
cd ecommerce_ai_chat/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8001

# 前端（在 ecommerce_ai_chat/frontend/ 目录）
cd ecommerce_ai_chat/frontend
npm install
npm run dev   # 默认 http://localhost:5173
```

### 环境变量（`ecommerce_ai_chat/backend/.env`）

```
OPENAI_API_KEY=...
DEEPSEEK_API_KEY=...
```

### 架构概览

**后端**（`ecommerce_ai_chat/backend/main.py`，FastAPI + SQLite）：
- JWT 鉴权（30 天有效期），`passlib` pbkdf2_sha256 密码哈希
- SQLAlchemy + SQLite（`ecommerce_chat.db`），两张表：`users`、`chat_sessions`
- AI 集成：`gpt-4o`（图像/视频分析）、`gpt-image-2`（图像生成，约 100 秒/张）、DeepSeek（文案优化）
- Clash 代理：所有 OpenAI 调用需要在 `http://127.0.0.1:7890` 运行代理

**前端**（`ecommerce_ai_chat/frontend/`，React 19 + Vite + TailwindCSS）：
- Vite 代理：`/api` → `http://localhost:8001`
- axios 发起 API 请求，`useRef` 规避 stale closure

### 关键异步模式

FastAPI 的 `async def` 端点内**禁止**直接调用同步 OpenAI SDK（会阻塞事件循环）。必须通过线程池包装：

```python
_executor = ThreadPoolExecutor(max_workers=8)

async def run_sync(fn, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, functools.partial(fn, *args, **kwargs))

# 调用示例
result = await run_sync(gpt_client.chat.completions.create, model="gpt-4o", messages=[...])
```

### 视频分析流程

视频文件通过 OpenAI Files API 上传（`purpose="vision"`），再用 `gpt-4o` 分析（`{"type": "file", "file": {"file_id": ...}}`），分析完成后自动删除文件。

---

## 全局测试规范（每次修改 ecommerce_ai_chat 后必须执行）

**每次对 `ecommerce_ai_chat/` 进行代码修改或功能新增后，必须在汇报完成前运行测试套件：**

```powershell
cd d:\workflow_project
.\ecommerce_ai_chat\run_tests.ps1
```

### 测试覆盖范围

| 模块 | 测试内容 |
|------|---------|
| `TestAuth` | 注册/登录成功、重复用户名、密码过短、错误密码、无效 Token |
| `TestSessions` | 会话 CRUD、鉴权隔离、跨用户访问拦截 |
| `TestEndpointAvailability` | 所有 AI 端点存在且鉴权生效、参数校验生效 |
| 前端构建 | `npm run build` 无编译/类型错误 |

### 强制规则

1. **运行脚本**：改动完成后执行 `run_tests.ps1`，查看汇总报告
2. **全部通过才能汇报**：若有失败项，必须先修复再告知用户任务完成
3. **新增功能同步补测试**：新路由须在 `test_api.py` 中添加对应的 `TestEndpointAvailability` 用例
4. **禁止跳过失败**：不能用 `pytest.mark.skip` 绕过失败，必须修复根因

### 测试文件位置

- 测试用例：`ecommerce_ai_chat/backend/test_api.py`
- 主控脚本：`ecommerce_ai_chat/run_tests.ps1`

---

### CSS 变量（`index.css`）

```css
--primary: #f97316;      /* 橙色主色 */
--primary-dark: #ea580c;
--primary-light: #fff7ed;
--bg: #f9fafb;
--border: #e5e7eb;
--accent: #111827;
```
