# iFund · 公募基金筛选与数据管理系统

一套自托管的公募基金数据管理与筛选工具：从公开数据源拉取基金名单、详情指标、持仓与历史净值，提供多维度筛选、净值走势可视化、筛选预设与镜像快照，并通过 MCP 把数据能力开放给本机 AI agent（如 OpenClaw）。

> 想了解完整的技术架构、数据模型与设计决策，见 [ARCHITECTURE.md](./ARCHITECTURE.md)。

## ✨ 功能特性

- **基金管理**：基金名单同步、详情指标（收益/回撤/夏普/仓位等）、前十大持仓、净值走势迷你图。
- **高级筛选**：关键词、名称包含/排除、分类、代码排除，以及数值区间与比较条件（夏普、回撤、规模、仓位、今年收益等），支持排序分页。
- **筛选预设**：保存常用筛选条件；每个预设可存「镜像快照」（点位时间结果）与「最新实时筛选」对比，直观看出新增/剔除的基金。
- **交易日历**：同步并查询交易日。
- **数据拉取**：详情/持仓/净值通过子进程异步拉取（akshare），带任务进度轮询；同类任务全局互斥防并发。
- **多用户隔离**：预设、镜像、访问令牌均按用户隔离。
- **对外集成（MCP）**：通过个人访问令牌（PAT）把只读/写入能力安全暴露给本机 agent。

## 🧱 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Python 3.12 · Flask 3.1 · flask-jwt-extended · bcrypt · pydantic · akshare |
| 数据 | SQLite（多后端抽象层，预留 MySQL）|
| 前端 | React 18 · TypeScript · Ant Design 5 · Vite 5 · Tailwind |
| 集成 | MCP（官方 Python SDK / FastMCP）· httpx |

## 📁 目录结构

```
ifund/
├── backend/            后端 Flask 应用
│   ├── app/            应用工厂、蓝图、DB 抽象、worker
│   ├── schema_sqlite.sql   SQLite 建表脚本
│   ├── requirements.txt
│   └── .env            本地配置（不入库）
├── frontend/           前端 React + Vite 应用
│   └── src/pages/      基金管理 / 基金筛选 / 交易日历 / 访问令牌
├── mcp_server/         MCP 服务器（对接 OpenClaw 等 agent）
├── ARCHITECTURE.md     高保真架构文档
├── start.sh            一键启动脚本
└── pyproject.toml      pylint 配置
```

## 🚀 快速开始

### 环境要求

- **Python 3.12+**（官方 MCP SDK 需要 3.10+）
- **Node.js 18+**

### 一键启动

```bash
./start.sh
```

脚本会自动：创建后端 venv 并装依赖 → 安装前端依赖并构建 → 启动后端（:8000）与前端开发服务（:9000）。

### 手动启动

后端：

```bash
cd backend
python3.12 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/flask --app app.main run --port 8000
```

前端（开发模式，:9000 代理 `/api` → :8000）：

```bash
cd frontend
npm install
npm run dev
```

生产模式下 `npm run build` 会把前端产物输出到 `backend/static`，由后端单端口（:8000）直接提供。

## ⚙️ 配置

在 `backend/.env` 中配置（可参考 `backend/.env.example`）：

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `SECRET_KEY` | JWT 签名密钥，**生产/对外暴露前必须设强随机值** | `dev-secret`（仅开发） |
| `DB_BACKEND` | 数据库后端 | `sqlite` |
| `DB_PATH` | SQLite 数据库文件路径 | `backend/data.db` |

> ⚠️ **安全**：`SECRET_KEY` 必须 ≥32 字节随机值，否则 JWT 可被伪造（启动时会对弱密钥告警）。生成方法：
> ```bash
> python3 -c "import secrets; print(secrets.token_hex(32))"
> ```
> 后端应保持绑定 `127.0.0.1`，不要直接暴露到公网。

## 🤖 MCP / OpenClaw 集成

后端能力可通过 MCP 服务器开放给本机 agent。认证使用**个人访问令牌（PAT）**：在网页端「访问令牌」页创建（明文仅显示一次），由 MCP 服务器自动换取短期 JWT 调用后端。

详见 [mcp_server/README.md](./mcp_server/README.md)。

## 🛠️ 开发约定

- **后端 lint**：`./backend/venv/bin/pylint app`，须保持 `10.00/10`。
- **前端类型检查**：`cd frontend && npx tsc --noEmit`。
- **前端 lint**：`cd frontend && npm run lint`。
- 后端业务文件统一使用 `from __future__ import annotations`（`mcp_server/server.py` 例外，原因见其文件头注释）。

## 📄 文档

- [ARCHITECTURE.md](./ARCHITECTURE.md) — 完整技术架构、数据模型、接口契约、从零复原步骤
- [mcp_server/README.md](./mcp_server/README.md) — MCP 服务器配置与工具清单
