# AKQuant Platform Phase 1 Design

## References

- Spec: `docs/zh/akquant_platform_position_spec.md`
- Plan: `docs/zh/akquant_platform_implementation_plan.md`

This document captures implementation decisions and scope for Phase 1 execution.

## Scope: Backend + CLI First

Phase 1a builds the backend core and CLI. Frontend follows in Phase 1b.

### Phase 1a Deliverables

1. **Project scaffolding** — `apps/akquant_platform/backend/`, `configs/`, `workspace/`
2. **Position models** — Pydantic models for positions, transactions, rules, audit log
3. **Repository** — YAML read/write for `current_positions.yaml`
4. **Calculator** — Moving weighted average cost, realized/unrealized PnL, position weight, status
5. **Rules engine** — Registry loader, rule evaluator, error isolation
6. **Intraday cache** — Download, TTL, refresh, cleanup, meta.json
7. **Service layer** — Orchestrates repository, calculator, rules, intraday
8. **CLI** — `scripts/positions_cli.py` with init/buy/sell/list/validate
9. **FastAPI** — Minimal API set (health, positions CRUD, intraday, data update, jobs)
10. **Job runner** — SQLite-backed task queue for data updates
11. **Unit tests** — Core logic tests per the test plan in spec section 7

### Phase 1b (later)

- React frontend (Vite + TypeScript + ECharts)
- Position management UI, intraday chart, transaction forms, rule UI

## Technology Choices

| Layer | Choice | Reason |
|---|---|---|
| Backend framework | FastAPI | Spec requirement |
| Data validation | Pydantic v2 | Standard with FastAPI |
| Task storage | SQLite (aiosqlite) | Spec: "v1 default SQLite" |
| Frontend (Phase 1b) | Vite + React + TypeScript | User preference |
| Charts (Phase 1b) | ECharts (echarts-for-react) | Financial chart support |
| Package management | pip with requirements.txt | Consistent with existing project |
| Python version | >= 3.10 | Consistent with existing pyproject.toml |

## Directory Structure

```text
apps/akquant_platform/
  backend/
    app/
      __init__.py
      main.py              # FastAPI app
      config.py             # Platform config loader
      positions/
        __init__.py
        models.py           # Pydantic models
        repository.py       # YAML read/write
        calculator.py       # Cost, PnL, status calculations
        rules.py            # Registry + rule evaluation
        service.py          # Business logic orchestration
        routes.py           # FastAPI router
      intraday/
        __init__.py
        cache.py            # Intraday download, TTL, cleanup
        routes.py           # FastAPI router
      jobs/
        __init__.py
        runner.py           # Task queue, SQLite-backed
        routes.py           # FastAPI router
    requirements.txt
    tests/
      __init__.py
      conftest.py
      test_models.py
      test_calculator.py
      test_repository.py
      test_rules.py
      test_service.py
      test_intraday.py
      test_cli.py

configs/
  platform.example.yaml
  positions/
    current_positions.example.yaml

workspace/
  registry.yaml
  position_configs/
    current_positions.yaml   # gitignored
  strategies/
  position_rules/

scripts/
  positions_cli.py            # New
  update_intraday_data.py     # New
```

## Implementation Order

Build bottom-up, each layer tested before the next:

1. Scaffolding + config
2. Models (Pydantic)
3. Calculator (pure logic, no I/O)
4. Repository (YAML read/write)
5. Rules (registry + evaluator)
6. Service (orchestration)
7. Intraday cache
8. CLI
9. FastAPI routes
10. Job runner
11. Integration tests

## Key Design Decisions

1. **Calculator is pure** — no file I/O, takes list of transactions and returns computed position. Makes testing trivial.
2. **Repository owns YAML** — single responsibility for file reads/writes, handles UUID generation and audit log persistence.
3. **Service coordinates** — calls repo to load/save, calculator to compute, rules to evaluate. No business logic leaks into routes.
4. **CLI and API share service** — both use the same service layer, ensuring consistent behavior.
5. **Rules import at runtime** — workspace_dir added to sys.path temporarily; import failures mark rules as invalid, don't crash the platform.
6. **Job runner is SQLite** — simple, local, no external dependencies. Jobs have queued/running/success/failed states.
