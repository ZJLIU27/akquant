# macOS 迁移说明

本文记录把当前 AKQuant 工作区迁移到 macOS 时的最小可执行路径。迁移目标是让核心 `Rust + Python` 包、本地 `FastAPI + React` 平台、数据更新脚本和用户 `workspace/` 都能在 Mac 上继续工作。

## 可行性结论

当前项目整体迁移到 macOS 可行，主要原因是：

- 核心包使用 `pyproject.toml`、`Cargo.toml`、`maturin`、`pyo3`，属于跨平台构建栈。
- Python 代码大量使用 `pathlib.Path`，没有依赖 Windows 盘符作为运行前提。
- 本地平台后端是 FastAPI，前端是 Vite + React，依赖链支持 macOS。
- 数据缓存使用 Parquet、YAML、SQLite 等跨平台格式。
- 仓库已经保留 Bash 脚本入口：`scripts/start_dev.sh`、`scripts/cargo-test.sh`、`scripts/dev-check.sh`。

## 不要直接迁移的内容

这些目录或文件是本机产物，不应从 Windows 复制到 macOS：

```text
.venv/
target/
apps/akquant_platform/frontend/node_modules/
apps/akquant_platform/frontend/dist/
__pycache__/
.pytest_cache/
.DS_Store
```

`data/` 是否迁移取决于你是否要保留已有 Parquet 缓存。它不是代码依赖；不迁移也可以在 Mac 上重新运行 `scripts/update_data.py` 生成。

## workspace 处理

`workspace/` 是用户自有策略、规则、真实持仓和注册配置的位置，并且当前可作为独立仓库维护。迁移主仓库时要单独处理它：

- 如果 `workspace/` 已经有自己的远程仓库，在 macOS 上单独 clone。
- 如果没有远程仓库，按普通目录复制即可。
- 不要把真实持仓、规则和策略并回主仓库目录。

平台默认配置仍然来自：

```text
configs/platform.example.yaml
configs/platform.yaml
workspace/registry.yaml
workspace/position_configs/current_positions.yaml
```

其中 `configs/platform.yaml` 是本地真实配置，不进入主仓库。

## macOS 环境准备

推荐先安装基础工具：

```bash
xcode-select --install
brew install uv rust node
```

如果不用 Homebrew，只要确保这些命令在 `PATH` 中可用即可：

```bash
uv --version
cargo --version
npm --version
```

## 初始化项目

在 macOS 上进入仓库根目录后运行：

```bash
bash scripts/setup_macos.sh
```

该脚本会做四件事：

1. `uv sync --extra dev`
2. 安装平台后端依赖：`apps/akquant_platform/backend/requirements.txt`
3. 构建本地 Rust Python 扩展：`uv run maturin develop`
4. 安装前端依赖：优先 `npm ci`，没有 lock 文件时回退到 `npm install`

## 启动本地平台

初始化完成后运行：

```bash
bash scripts/start_dev.sh
```

默认地址：

```text
Backend:  http://localhost:8000
Frontend: http://localhost:3000
```

前端会通过 Vite proxy 访问后端 `/api`。

## 建议在 Mac 上验证

你可以按改动范围选择验证，不需要每次全量跑完：

```bash
uv run pytest tests/test_update_data.py -q
uv run python -m pytest apps/akquant_platform/backend/tests -q
cd apps/akquant_platform/frontend && npm run build
```

涉及 Rust/Python binding 时再跑：

```bash
uv run maturin develop
bash scripts/cargo-test.sh -q
```

## 常见问题

### `uvicorn` 找不到

先运行：

```bash
bash scripts/setup_macos.sh
```

平台后端依赖不在主包的基础依赖里，setup 脚本会额外安装 `apps/akquant_platform/backend/requirements.txt`。

### 前端原生包架构不匹配

不要复用 Windows 的 `node_modules/`。在 macOS 上删除后重新安装：

```bash
cd apps/akquant_platform/frontend
rm -rf node_modules dist
npm ci
```

### Rust 扩展或 Python 动态库加载失败

先确认 Python 和 Rust 架构一致，Apple Silicon 上不要混用 x86_64 Python 和 arm64 Rust。然后重新构建：

```bash
uv run maturin develop
```

如果是 `cargo test` 相关动态库问题，使用仓库脚本：

```bash
bash scripts/cargo-test.sh -q
```

### AkShare 拉取失败

这通常和目标机器网络、接口限流或上游返回有关，不代表迁移失败。先用已有本地 Parquet 或小范围 symbol 验证：

```bash
uv run python scripts/update_data.py --data-dir ./data --symbols 000001 --workers 1
```
