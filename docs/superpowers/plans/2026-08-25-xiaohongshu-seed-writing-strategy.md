# Xiaohongshu Seed Writing Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Inject the global “红书种草写作策略 v1” only when the generation worker creates a copy draft.

**Architecture:** A pure strategy module returns a versioned instruction string. `GenerationWorker` appends that instruction to the frozen copy-type generation requirements immediately before it calls `ModelAdapter.generate_copy`; no Brief parser, assistant, QC workflow, API contract, or UI invokes it. The generated run snapshot receives the strategy name and version before slot creation so historical batches remain reproducible.

**Tech Stack:** Python 3.12, FastAPI worker, Pydantic generation context, pytest.

---

### Task 1: Define the versioned generation-only strategy

**Files:**
- Create: `backend/app/generation/xiaohongshu_seed_strategy.py`
- Test: `backend/tests/unit/test_xiaohongshu_seed_strategy.py`

- [x] **Step 1: Write the failing test**

```python
from backend.app.generation.xiaohongshu_seed_strategy import (
    STRATEGY_NAME,
    STRATEGY_VERSION,
    build_instruction,
)


def test_strategy_has_a_stable_name_version_and_safe_generation_instruction():
    instruction = build_instruction()
    assert STRATEGY_NAME == "红书种草写作策略"
    assert STRATEGY_VERSION == "v1"
    assert "场景" in instruction
    assert "不得编造" in instruction
    assert "绝对化" in instruction
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv\\Scripts\\python.exe -m pytest backend/tests/unit/test_xiaohongshu_seed_strategy.py -q`

Expected: import failure because the module does not exist.

- [x] **Step 3: Write minimal implementation**

```python
STRATEGY_NAME = "红书种草写作策略"
STRATEGY_VERSION = "v1"


def build_instruction() -> str:
    return """【红书种草写作策略 v1】..."""
```

The instruction must require a need-first structure, concrete fact-supported detail, conditional personal framing, short mobile-friendly paragraphs, and a soft close. It must prohibit invented testing/feedback/data/defects, unsupported claims, and absolute language.

- [x] **Step 4: Run test to verify it passes**

Run: `.venv\\Scripts\\python.exe -m pytest backend/tests/unit/test_xiaohongshu_seed_strategy.py -q`

Expected: `1 passed`.

### Task 2: Invoke and freeze the strategy only for generation

**Files:**
- Modify: `backend/app/generation/service.py`
- Modify: `backend/app/generation/worker.py`
- Modify: `backend/tests/integration/test_generation_run.py`

- [x] **Step 1: Write failing integration tests**

```python
snapshot = json.loads(run["configuration_snapshot_json"])
assert snapshot["generation_strategy"] == {
    "name": "红书种草写作策略", "version": "v1"
}
```

Use a capture adapter with `generate_copy` to assert that the supplied `GenerationContext.description_requirements` contains `【红书种草写作策略 v1】` and that the original type requirements remain present.

- [x] **Step 2: Run tests to verify they fail**

Run: `.venv\\Scripts\\python.exe -m pytest backend/tests/integration/test_generation_run.py -q`

Expected: snapshot key and injected instruction assertions fail.

- [x] **Step 3: Implement the invocation**

```python
snapshot["generation_strategy"] = {
    "name": STRATEGY_NAME,
    "version": STRATEGY_VERSION,
}
...
description_requirements=[
    build_instruction(),
    *json.loads(copy_type["description_requirements_json"]).values(),
]
```

The worker may call the strategy only in the queued generation branch, immediately before `generate_copy`. It must not include the strategy in `_run_qc` or assistant/brief paths.

- [x] **Step 4: Run focused and full backend verification**

Run: `.venv\\Scripts\\python.exe -m pytest backend/tests -q; .venv\\Scripts\\python.exe -m ruff check backend/app backend/tests`

Expected: all tests pass and Ruff reports no errors.

- [ ] **Step 5: Commit**

```bash
git add backend docs/superpowers/plans/2026-08-25-xiaohongshu-seed-writing-strategy.md task_plan.md progress.md
git commit -m "feat: add xiaohongshu seed writing strategy"
```
