# AKQuant SubAgent 项目导览

这份文档用于让 SubAgent 在进入 `D:\Git\akquant` 后快速判断项目结构、构建方式和开发规范。优先读本文，再按任务范围读取相关文件，不要默认全仓库扫描。

## 1. 项目定位

AKQuant 是一个 Rust + Python 混合量化框架：

- Rust 核心在 `src/`，通过 `pyo3` 和 `maturin` 暴露 Python 扩展模块。
- Python 包在 `python/akquant/`，负责策略接口、回测封装、因子、绘图、网关、工具函数等 Python 层能力。
- 测试在 `tests/`，包含核心回测、策略、报告、因子、数据更新脚本和 golden baseline。
- 本地平台应用在 `apps/akquant_platform/`，是新增的 React + FastAPI 操作界面。
- 平台计划和稳定契约在 `docs/zh/akquant_platform_implementation_plan.md` 与 `docs/zh/akquant_platform_position_spec.md`。

## 2. 目录速查

```text
D:\Git\akquant\
  src/                         Rust core and Python bindings
  python/akquant/              Python package source
  tests/                       Python regression tests and golden tests
  scripts/                     Maintenance, docs checks, data update, platform helpers
  docs/zh/                     Chinese docs and platform planning docs
  configs/                     Tracked example platform configs
  data/                        Local daily and intraday parquet cache
  apps/akquant_platform/
    backend/                   FastAPI backend
    frontend/                  React + Vite frontend
  workspace/                   User-owned strategies, rules, positions; separate git repo/workspace
```

重点边界：

- `workspace/` 是用户自有策略、持仓规则、真实持仓配置的工作区，后续可作为独立仓库维护。平台通过 `workspace/registry.yaml` 显式注册策略和规则，不自动扫描 Python 文件。
- `configs/platform.example.yaml` 是主仓库跟踪的示例配置；本地真实配置默认是 `configs/platform.yaml`。
- 日线数据默认在 `data/{symbol}.parquet`；分时缓存默认在 `data/intraday/{symbol}/{YYYY-MM-DD}.parquet`。
- 数据更新复用 `scripts/update_data.py`，不要为平台另造一套日线下载逻辑。

## 3. 构建方式

### 3.1 Python/Rust 包

项目由 `pyproject.toml` 和 `Cargo.toml` 共同定义：

- Python 构建后端：`maturin`
- Rust crate：`akquant`
- Python 源码目录：`python`
- 扩展模块名：`akquant.akquant`
- Python 要求：`>=3.10`

常用命令：

```powershell
uv run maturin develop
uv run pytest tests/test_update_data.py -q
uv run pytest tests/test_engine.py -q
uv run ruff check python/akquant tests
uv run mypy python/akquant
```

如果当前环境没有 `uv`，先确认本机项目环境，不要直接改锁文件。Windows 下也可以按已安装解释器情况使用：

```powershell
python -m pytest tests/test_update_data.py -q
```

已有聚合检查脚本：

```bash
scripts/dev-check.sh
```

注意：该脚本是 Bash 脚本；在当前 Windows 环境中不要假设 WSL/Bash 一定可用。

### 3.2 FastAPI 后端

后端位置：

```text
apps/akquant_platform/backend/
```

主要入口：

```text
apps/akquant_platform/backend/app/main.py
```

模块职责：

- `app/config.py`：读取 `configs/platform.yaml`，不存在时回退到 `configs/platform.example.yaml`，并把路径解析到仓库根目录。
- `app/positions/`：持仓模型、仓储、计算、规则执行、API 路由。
- `app/intraday/`：分时缓存和数据路由。
- `app/jobs/`：后台任务路由与 runner。
- `app/stocks/`：股票搜索/标的目录相关能力。

启动后端：

```powershell
cd apps\akquant_platform\backend
py -3 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

后端依赖在：

```text
apps/akquant_platform/backend/requirements.txt
```

后端局部测试：

```powershell
python -m pytest apps\akquant_platform\backend\tests -q
```

### 3.3 React 前端

前端位置：

```text
apps/akquant_platform/frontend/
```

技术栈由 `package.json` 定义：

- React
- TypeScript
- Vite
- ECharts
- React Router
- ESLint

常用命令：

```powershell
cd apps\akquant_platform\frontend
npm install
npm run dev -- --host
npm run build
npm run lint
```

前端源码重点：

- `src/api/client.ts`：后端 API client。
- `src/pages/PositionListPage.tsx`：持仓列表页。
- `src/pages/PositionDetailPage.tsx`：持仓详情页。
- `src/components/`：图表、交易表单、交易列表、规则面板、股票搜索等组件。
- `src/theme/`：全局样式和主题变量。

### 3.4 一键本地平台开发

Windows 本地平台启动脚本：

```powershell
scripts\start_dev.bat
```

该脚本会启动：

- 后端：`http://localhost:8000`
- 前端：`http://localhost:3000`

如果端口被占用，先查占用进程，不要直接改业务代码。

## 4. 开发规范

### 4.1 先判断任务范围

- 修改 Rust core：优先读 `src/lib.rs`、相关 `src/<domain>/` 模块、对应 Python binding 和测试。
- 修改 Python 包：优先读 `python/akquant/` 下相关模块与 `tests/test_*.py`。
- 修改平台后端：优先读 `apps/akquant_platform/backend/app/<domain>/` 和对应 `backend/tests/test_*.py`。
- 修改平台前端：优先读 `apps/akquant_platform/frontend/src/api/client.ts`、目标 page/component 和主题文件。
- 修改平台行为契约：先读 `docs/zh/akquant_platform_position_spec.md`；如果是 roadmap/phase，再读 `docs/zh/akquant_platform_implementation_plan.md`。

### 4.2 保持边界清楚

- 不要把用户自有策略、规则、真实持仓并回主包；它们属于 `workspace/`。
- 不要绕过 `workspace/registry.yaml` 做隐式自动扫描。
- 不要把真实本地配置写进示例配置；示例留在 `configs/*.example.*`。
- 不要把 `node_modules/`、`dist/`、`__pycache__/`、`.pytest_cache/`、本地数据库等生成物纳入修改。
- 修改数据更新逻辑时，直接检查 parquet 结果，不要只看脚本输出。

### 4.3 测试选择

按改动范围选择最小但有效的验证：

```powershell
# 数据更新脚本
python -m pytest tests\test_update_data.py -q

# Python 包核心行为
python -m pytest tests\test_engine.py -q
python -m pytest tests\test_strategy_extras.py -q

# 平台后端
python -m pytest apps\akquant_platform\backend\tests -q

# 前端
cd apps\akquant_platform\frontend
npm run lint
npm run build
```

涉及 Rust/Python binding 时，先构建本地扩展：

```powershell
uv run maturin develop
```

### 4.4 代码风格

Python/Rust package:

- Python 使用 Ruff，行宽 88，目标版本 `py310`。
- mypy 配置在 `pyproject.toml`，`python/akquant` 要保持类型约束。
- 公共 API 改动要补或更新测试。

平台后端：

- 使用 Pydantic model 表达请求/响应结构。
- 文件路径通过 `app/config.py` 的配置解析，不要在业务模块硬编码仓库绝对路径。
- 持仓状态由交易流水计算，不直接写入 YAML。
- 作废交易用 `voided` 语义，不物理删除历史流水。

平台前端：

- API 类型和请求集中在 `src/api/client.ts`，组件不要散落硬编码 fetch。
- 图表和表单组件保持单一职责；页面负责组合数据流。
- A 股图表颜色按红涨绿跌处理。

### 4.5 文档规范

- 平台实施计划写入 `docs/zh/akquant_platform_implementation_plan.md`。
- 稳定数据结构、配置、规则执行契约写入 `docs/zh/akquant_platform_position_spec.md`。
- 面向 Agent 的项目导览维护在本文。
- 如果代码行为改变了既有契约，同步更新对应文档。

## 5. 常见入口

```text
scripts/update_data.py
  Daily AkShare-to-Parquet incremental updater.

scripts/positions_cli.py
  Platform position helper CLI.

apps/akquant_platform/backend/app/main.py
  FastAPI application entry.

apps/akquant_platform/frontend/src/App.tsx
  React app composition entry.

python/akquant/__init__.py
  Python package public exports.

src/lib.rs
  Rust crate and Python extension root.
```

## 6. 给 SubAgent 的执行建议

1. 先读本文，确定任务属于 core package、platform backend、platform frontend、docs/spec、data script 还是 workspace。
2. 只读取目标范围内的 3-8 个关键文件，不要默认扫全仓库。
3. 改代码前看对应测试；没有测试时按风险补最小回归测试。
4. 完成后运行与改动范围匹配的检查命令，并在回复里说明已跑和未跑的验证。
5. 如果发现工作区已有无关改动，保留它们，不要回滚。
