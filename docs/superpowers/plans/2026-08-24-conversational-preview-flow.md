# Conversational Project Setup and Preview Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user describe a copywriting task in conversation, review an editable proposal, generate at most three preview copies, and continue the approved preview batch to its configured total without breaking existing QC or export audit history.

**Architecture:** Add a server-owned assistant session that records messages and returns structured proposals; proposals are only persisted after an explicit “应用到任务” action. Extend an existing generation run with a preview phase: create up to three deterministic item slots, pause for approval, and append the remaining slots to the same run ID. React renders a two-panel workspace while existing project/type/QC pages remain Advanced configuration.

**Tech Stack:** React 19, TypeScript, Vite, FastAPI, Pydantic v2, SQLite, existing CLIPROXY/Fake ModelAdapter, pytest, Vitest, Playwright.

---

## Locked product decisions

| Area | Decision |
|---|---|
| Primary entry | New projects open a conversation workspace; old configuration pages remain available under “高级配置”. |
| AI authority | AI may propose data and ask up to three blocking questions; it cannot silently write project facts, rules, types, quantities, or start a run. |
| Preview | Default is min(3, configured total); user can explicitly choose “直接生成全部”. |
| Multiple types | Select one item per type in saved type order, then round-robin until 3 slots are selected. |
| Continue | “按此方向生成剩余 N 篇” creates missing item slots in the same generation run and retains preview QC/audit records. |
| Revision | A configuration change after preview requires a new preview/full batch; a run’s frozen snapshot is never changed. |
| Export | A run waiting for preview approval cannot be exported. |
| Board | Keep the current three user groups; detailed five internal statuses remain card metadata and API state. |

## Files and ownership

| Path | Change |
|---|---|
| `backend/app/db/migrations/005_assistant_and_preview_runs.sql` | Assistant persistence plus preview fields on generation runs. |
| `backend/app/domain/schemas.py` | Strict assistant, action, and preview request schemas. |
| `backend/app/model/protocol.py`, `fake.py`, `cliproxy.py` | Structured task-planning model operation. |
| `backend/app/assistant/service.py`, `backend/app/api/assistant.py` | Conversation, proposal validation, explicit action application. |
| `backend/app/generation/service.py`, `worker.py`, `api/runs.py` | Preview allocation, approval pause, same-run continuation. |
| `backend/app/db/repositories.py` | Sessions/messages/action receipts and atomic slot appending. |
| `frontend/src/features/assistant/*` | Transcript, composer, proposal card. |
| `frontend/src/features/workspace/ProjectWorkspacePage.tsx` | Primary two-panel workspace. |
| `frontend/src/api/*`, `router.tsx`, `AppShell.tsx` | Contracts, services, mock mode, primary navigation. |
| `frontend/src/features/board/*`, `export/*` | Preview status, continuation and export guard presentation. |

### Task 1: Define strict contracts

**Files:**
- Modify: `backend/app/domain/schemas.py`
- Modify: `backend/app/model/protocol.py`
- Modify: `frontend/src/api/contracts.ts`
- Test: `backend/tests/unit/test_assistant_schemas.py`

- [x] **Step 1: Write failing schema tests**

~~~python
def test_unknown_assistant_action_is_rejected():
    with pytest.raises(ValidationError):
        AssistantAction(client_action_id="a1", kind="delete_database", payload={})

def test_empty_action_id_is_rejected():
    with pytest.raises(ValidationError):
        AssistantAction(client_action_id="", kind="set_project", payload={"name": "夏季种草"})
~~~

- [x] **Step 2: Run the tests**

Run: `E:\xixiAi\batch-copy-qc\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_assistant_schemas.py -q`

Expected: FAIL because the schemas do not exist.

- [x] **Step 3: Add minimal shared models**

~~~python
class AssistantAction(StrictModel):
    client_action_id: str = Field(min_length=1, max_length=100)
    kind: Literal["set_project", "replace_project_findings", "upsert_copy_type",
                  "replace_project_rules", "start_generation"]
    payload: dict[str, Any]

class AssistantPlan(StrictModel):
    summary: str = Field(min_length=1, max_length=2000)
    blockers: list[str] = Field(default_factory=list, max_length=3)
    assumptions: list[str] = Field(default_factory=list, max_length=10)
    actions: list[AssistantAction] = Field(default_factory=list, max_length=20)

class AssistantMessageCreate(StrictModel):
    content: str = Field(min_length=1, max_length=12000)

class PreviewConfirmation(StrictModel):
    expected_preview_item_count: int = Field(ge=1, le=3)
~~~

Add matching TypeScript types plus `GenerationMode = "preview" | "full"` and preview fields on `GenerationRun`. Add `plan_project_setup(...)->AssistantPlan` to `ModelAdapter`.

- [x] **Step 4: Verify**

Run: `E:\xixiAi\batch-copy-qc\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_assistant_schemas.py -q; npm.cmd --prefix frontend run typecheck`

Expected: PASS.

- [ ] **Step 5: Commit**

`git add backend/app/domain/schemas.py backend/app/model/protocol.py frontend/src/api/contracts.ts backend/tests/unit/test_assistant_schemas.py; git commit -m "feat: define assistant and preview contracts"`

### Task 2: Persist assistant history and preview phase

**Files:**
- Create: `backend/app/db/migrations/005_assistant_and_preview_runs.sql`
- Modify: `backend/app/db/repositories.py`
- Test: `backend/tests/integration/test_assistant_repository.py`

- [x] **Step 1: Write failing repository tests**

~~~python
def test_assistant_messages_are_saved_in_order(repository):
    session = repository.create_or_get_assistant_session("project-1")
    repository.append_assistant_message(session["id"], "user", "写 20 篇通勤文案")
    repository.append_assistant_message(session["id"], "assistant", "我会先做预览", plan={"summary": "x", "blockers": [], "assumptions": [], "actions": []})
    assert [m["role"] for m in repository.list_assistant_messages(session["id"])] == ["user", "assistant"]

def test_preview_run_has_full_target_and_three_preview_slots(repository):
    run = repository.create_generation_run("project-1", 20, {}, generation_mode="preview", preview_item_count=3)
    assert (run["requested_count"], run["generation_phase"], run["preview_item_count"]) == (20, "preview_running", 3)
~~~

- [x] **Step 2: Run the tests**

Run: `E:\xixiAi\batch-copy-qc\.venv\Scripts\python.exe -m pytest backend/tests/integration/test_assistant_repository.py -q`

Expected: FAIL.

- [x] **Step 3: Add migration and repository methods**

Migration requirements:

~~~sql
ALTER TABLE generation_runs ADD COLUMN generation_mode TEXT NOT NULL DEFAULT 'full'
  CHECK(generation_mode IN ('preview','full'));
ALTER TABLE generation_runs ADD COLUMN generation_phase TEXT NOT NULL DEFAULT 'full_running'
  CHECK(generation_phase IN ('preview_running','awaiting_preview_approval','full_running','completed'));
ALTER TABLE generation_runs ADD COLUMN preview_item_count INTEGER NOT NULL DEFAULT 0
  CHECK(preview_item_count BETWEEN 0 AND 3);
ALTER TABLE generation_runs ADD COLUMN preview_confirmed_at TEXT;

CREATE TABLE assistant_sessions (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE assistant_messages (
  id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES assistant_sessions(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK(role IN ('user','assistant','system')), content TEXT NOT NULL,
  plan_json TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE assistant_action_receipts (
  id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES assistant_sessions(id) ON DELETE CASCADE,
  client_action_id TEXT NOT NULL, result_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(session_id, client_action_id)
);
~~~

Implement `create_or_get_assistant_session`, `append_assistant_message`, `list_assistant_messages`, `get_action_receipt`, `save_action_receipt`, and transactional `create_item_slots(run_id, allocations)`. Slot insertion must retain the existing unique key and fail rather than duplicate.

- [x] **Step 4: Verify migrations and repositories**

Run: `E:\xixiAi\batch-copy-qc\.venv\Scripts\python.exe -m pytest backend/tests/integration/test_assistant_repository.py backend/tests -q`

Expected: PASS.

- [ ] **Step 5: Commit**

`git add backend/app/db/migrations/005_assistant_and_preview_runs.sql backend/app/db/repositories.py backend/tests/integration/test_assistant_repository.py; git commit -m "feat: persist assistant and preview run state"`

### Task 3: Add controlled assistant API

**Files:**
- Create: `backend/app/assistant/__init__.py`
- Create: `backend/app/assistant/service.py`
- Create: `backend/app/api/assistant.py`
- Modify: `backend/app/model/fake.py`
- Modify: `backend/app/model/cliproxy.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/contract/test_assistant_api.py`

- [ ] **Step 1: Write failing contract tests**

~~~python
def test_message_returns_a_plan_without_mutating_the_project(client, project):
    response = client.post(f"/api/projects/{project['id']}/assistant/messages", json={"content": "给新品写 20 篇通勤种草"})
    assert response.status_code == 201
    assert response.json()["plan"]["actions"]
    assert client.get(f"/api/projects/{project['id']}").json()["status"] == "draft"

def test_action_application_is_idempotent(client, project):
    payload = {"actions": [{"client_action_id": "set-name", "kind": "set_project", "payload": {"name": "通勤种草"}}]}
    assert client.post(f"/api/projects/{project['id']}/assistant/actions:apply", json=payload).status_code == 200
    assert client.post(f"/api/projects/{project['id']}/assistant/actions:apply", json=payload).status_code == 200
~~~

- [ ] **Step 2: Run focused tests**

Run: `E:\xixiAi\batch-copy-qc\.venv\Scripts\python.exe -m pytest backend/tests/contract/test_assistant_api.py -q`

Expected: FAIL with route-not-found.

- [ ] **Step 3: Implement service and routes**

Expose:

~~~text
GET  /api/projects/{project_id}/assistant/session
POST /api/projects/{project_id}/assistant/messages
POST /api/projects/{project_id}/assistant/actions:apply
~~~

`AssistantService.reply` appends the user message, calls `plan_project_setup`, and persists the assistant plan. `apply_actions` validates all actions before changing anything, uses existing project/copy-type/rule/generation services, and stores an action receipt. If a plan has blockers, `start_generation` returns `ASSISTANT_BLOCKERS_UNRESOLVED` (409). Fake mode returns deterministic plans; CLIPROXY uses strict Responses structured output.

- [ ] **Step 4: Verify**

Run: `E:\xixiAi\batch-copy-qc\.venv\Scripts\python.exe -m pytest backend/tests/contract/test_assistant_api.py backend/tests/contract -q`

Expected: PASS; posting a message alone changes no project data.

- [ ] **Step 5: Commit**

`git add backend/app/assistant backend/app/api/assistant.py backend/app/model backend/app/main.py backend/tests/contract/test_assistant_api.py; git commit -m "feat: add controlled setup assistant"`

### Task 4: Generate preview and continue the same run

**Files:**
- Modify: `backend/app/generation/service.py`
- Modify: `backend/app/generation/worker.py`
- Modify: `backend/app/api/runs.py`
- Modify: `backend/app/db/repositories.py`
- Test: `backend/tests/integration/test_preview_generation.py`
- Test: `backend/tests/contract/test_runs_api.py`

- [ ] **Step 1: Write failing lifecycle tests**

~~~python
def test_preview_creates_three_representative_slots_then_pauses(client, configured_project):
    run = client.post(f"/api/projects/{configured_project}/generation-runs", json={"generation_mode": "preview"}).json()
    assert run["total_requested"] == 20
    assert run["preview_item_count"] == 3
    eventually(lambda: client.get(f"/api/generation-runs/{run['id']}").json()["generation_phase"] == "awaiting_preview_approval")

def test_confirm_preview_appends_to_the_original_run(client, configured_project):
    run = create_and_finish_preview(client, configured_project)
    response = client.post(f"/api/generation-runs/{run['id']}/preview:confirm", json={"expected_preview_item_count": 3})
    assert response.status_code == 200
    assert response.json()["id"] == run["id"]
    assert response.json()["generation_phase"] == "full_running"
~~~

- [ ] **Step 2: Run focused tests**

Run: `E:\xixiAi\batch-copy-qc\.venv\Scripts\python.exe -m pytest backend/tests/integration/test_preview_generation.py backend/tests/contract/test_runs_api.py -q`

Expected: FAIL.

- [ ] **Step 3: Implement allocation and phase transition**

Extend `RunCreate` with `generation_mode: Literal["preview", "full"] = "preview"`. Preserve `requested_count` as the configured total. Create only selected preview slots when in preview mode. In `summary`, set `awaiting_preview_approval` only after every preview item has terminal generation status; the worker must not enqueue additional items.

Add `GenerationService.confirm_preview(run_id, expected_preview_item_count)`. Within one immediate transaction it verifies phase/count, creates every missing slot from the frozen snapshot, sets `full_running` and `preview_confirmed_at`, and returns only new IDs for enqueueing. Repeat calls return the same run and no new IDs.

Add `POST /api/generation-runs/{run_id}/preview:confirm`; include mode, phase, preview count, generated and pending counts in public run responses.

- [ ] **Step 4: Verify generation regressions**

Run: `E:\xixiAi\batch-copy-qc\.venv\Scripts\python.exe -m pytest backend/tests/integration/test_preview_generation.py backend/tests/integration/test_qc_workflow.py backend/tests -q`

Expected: PASS. Restart and repeated confirmation never create duplicate slots.

- [ ] **Step 5: Commit**

`git add backend/app/generation backend/app/api/runs.py backend/app/db/repositories.py backend/tests/integration/test_preview_generation.py backend/tests/contract/test_runs_api.py; git commit -m "feat: add same-run preview continuation"`

### Task 5: Build the conversation-first workspace

**Files:**
- Create: `frontend/src/features/assistant/AssistantConversation.tsx`
- Create: `frontend/src/features/assistant/AssistantPlanCard.tsx`
- Create: `frontend/src/features/assistant/AssistantConversation.test.tsx`
- Create: `frontend/src/features/workspace/ProjectWorkspacePage.tsx`
- Create: `frontend/src/features/workspace/ProjectWorkspacePage.test.tsx`
- Modify: `frontend/src/api/service.ts`
- Modify: `frontend/src/api/mockService.ts`
- Modify: `frontend/src/app/router.tsx`
- Modify: `frontend/src/features/shell/AppShell.tsx`
- Modify: `frontend/src/styles/global.css`

- [ ] **Step 1: Write failing UI tests**

~~~tsx
it("requires explicit application of the assistant proposal", async () => {
  renderWorkspace();
  await user.type(screen.getByRole("textbox", { name: "告诉我你想做什么" }), "给新品做 20 篇通勤种草");
  await user.click(screen.getByRole("button", { name: "发送" }));
  expect(await screen.findByText("我准备这样做")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "应用到任务" }));
  expect(await screen.findByText("已更新任务配置")).toBeInTheDocument();
});

it("starts three previews and offers same-run continuation", async () => {
  renderConfiguredWorkspace();
  await user.click(screen.getByRole("button", { name: "先生成 3 篇预览" }));
  expect(await screen.findByRole("button", { name: "按此方向生成剩余 17 篇" })).toBeInTheDocument();
});
~~~

- [ ] **Step 2: Run focused UI tests**

Run: `npm.cmd --prefix frontend test -- --run src/features/assistant/AssistantConversation.test.tsx src/features/workspace/ProjectWorkspacePage.test.tsx`

Expected: FAIL.

- [ ] **Step 3: Implement the UI**

Add API methods `getAssistantSession`, `sendAssistantMessage`, `applyAssistantActions`, `createGenerationRun(projectId, generationMode)`, and `confirmPreview`. Mock mode must return a deterministic proposal and a ready three-item preview.

Desktop workspace uses two panels: left is transcript/composer; right is task summary, blockers, preview/full actions, preview continuation, and the existing three-group board. Clearly label assumptions. “应用到任务” is required before mutations. On small screens stack conversation first.

Route `/projects/:id` to workspace. Primary navigation becomes 工作台 / 文案看板 / 飞书输出. Add compact 高级配置 links to 项目内容 / 帖子类型 / QC 要求.

- [ ] **Step 4: Verify frontend quality**

Run: `npm.cmd --prefix frontend test -- --run; npm.cmd --prefix frontend run typecheck; npm.cmd --prefix frontend run build`

Expected: PASS; keyboard users can send, inspect, apply, preview and continue.

- [ ] **Step 5: Commit**

`git add frontend/src/features/assistant frontend/src/features/workspace frontend/src/api frontend/src/app/router.tsx frontend/src/features/shell/AppShell.tsx frontend/src/styles/global.css; git commit -m "feat: add conversational project workspace"`

### Task 6: Make board/export preview-aware and finish verification

**Files:**
- Modify: `frontend/src/features/board/BoardPage.tsx`
- Modify: `frontend/src/features/board/BoardStats.tsx`
- Modify: `frontend/src/features/export/ExportPage.tsx`
- Modify: `backend/app/export/service.py`
- Test: `frontend/src/features/board/BoardPage.test.tsx`
- Test: `frontend/src/features/export/ExportPage.test.tsx`
- Test: `backend/tests/integration/test_export_preview_guard.py`
- Create: `e2e/specs/conversational-preview.spec.ts`
- Modify: `README.md`
- Modify: `docs/frontend-visual-spec-v0.1.md`
- Modify: `docs/implementation-review-checklist.md`

- [ ] **Step 1: Write failing board/export tests**

~~~tsx
it("shows a completed preview and continues the original batch", async () => {
  renderBoardWithAwaitingPreviewApproval();
  expect(await screen.findByText("3 篇预览已就绪")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "按此方向生成剩余 17 篇" }));
  expect(await screen.findByText("正在生成剩余 17 篇")).toBeInTheDocument();
});
~~~

~~~python
def test_export_rejects_an_unapproved_preview(client, preview_run):
    response = client.post(f"/api/projects/{preview_run['project_id']}/exports", json={"generation_run_id": preview_run["id"]})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PREVIEW_APPROVAL_REQUIRED"
~~~

- [ ] **Step 2: Run focused tests**

Run: `E:\xixiAi\batch-copy-qc\.venv\Scripts\python.exe -m pytest backend/tests/integration/test_export_preview_guard.py -q; npm.cmd --prefix frontend test -- --run src/features/board/BoardPage.test.tsx src/features/export/ExportPage.test.tsx`

Expected: FAIL.

- [ ] **Step 3: Implement guard and presentation**

Show preview target, remaining count, “3 篇预览已就绪”, and continuation above the existing three groups. Disable export UI for awaiting approval and return `PREVIEW_APPROVAL_REQUIRED` (409) from export service to prevent API bypass. Do not change the existing completed-item filter.

Add Playwright coverage: create a project, send a message, apply proposal, generate preview, verify one run ID, confirm it, and verify the same run ID continues. Update README, visual spec and implementation checklist with proposal acceptance, preview allocation, same-run continuation and advanced configuration.

- [ ] **Step 4: Run full verification**

Run: `E:\xixiAi\batch-copy-qc\.venv\Scripts\python.exe -m pytest backend/tests -q -p no:cacheprovider; E:\xixiAi\batch-copy-qc\.venv\Scripts\ruff.exe check backend; npm.cmd --prefix frontend test -- --run; npm.cmd --prefix frontend run typecheck; npm.cmd --prefix frontend run build; npm.cmd --prefix frontend run test:e2e`

Expected: all checks PASS.

- [ ] **Step 5: Commit**

`git add backend/app/export/service.py backend/tests/integration/test_export_preview_guard.py frontend/src/features/board frontend/src/features/export e2e/specs/conversational-preview.spec.ts README.md docs/frontend-visual-spec-v0.1.md docs/implementation-review-checklist.md; git commit -m "test: cover conversational preview workflow"`

## Acceptance checklist

- [ ] A user can describe a task in one message and receive an understandable proposal.
- [ ] No proposal writes persistent configuration without explicit approval.
- [ ] Default generation produces at most three representative preview items.
- [ ] Confirmation creates the remaining slots under the same run ID.
- [ ] Repeated confirmation and worker restart cannot duplicate slots/model calls.
- [ ] Board retains three user-facing groups and detailed internal card status.
- [ ] Export rejects an unapproved preview in UI and API.
- [ ] Manual project/type/QC/review/export paths remain functional as advanced configuration.

## Self-review

**Spec coverage:** Tasks 1–3 implement conversation with controlled writes; Task 4 implements preview and continuation; Task 5 makes it the primary UX; Task 6 locks board/export behaviour, E2E and docs.

**Placeholder scan:** Every task has exact paths, concrete test examples, commands, expected results, implementation boundaries, and a commit.

**Type consistency:** `AssistantPlan`, `AssistantAction`, `generation_mode`, `generation_phase`, `preview_item_count`, and `PreviewConfirmation.expected_preview_item_count` are defined once and used unchanged.
