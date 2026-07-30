# Intelligent Coach, Curriculum, and Daily Radar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace fixed tutor replies and generic tasks with an intent-aware AI coach, a four-track evidence-gated curriculum, and an observable daily 08:00 radar pipeline.

**Architecture:** Keep curriculum selection deterministic in the domain layer, use Pydantic-validated LangGraph workflows only for task drafting and tutor interpretation, and expose shared radar execution through both APScheduler and authenticated APIs. Persist backward-compatible task details, radar run metadata, and expiring action proposals; stream typed SSE events to the existing React drawer.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, LangGraph, httpx, APScheduler, PostgreSQL/pgvector, React, TypeScript, Vitest, Playwright-compatible Testing Library, Docker Compose.

**Execution note:** The repository owner requested inline execution by the current primary agent. Do not delegate any task or use Coze.

---

### Task 1: Versioned Curriculum and Detailed Task Contract

**Files:**
- Create: `services/api/src/techgrowth_api/domain/curriculum.py`
- Modify: `services/api/src/techgrowth_api/domain/tasks.py`
- Create: `services/api/tests/test_curriculum.py`
- Modify: `services/api/tests/test_task_policy.py`

- [ ] **Step 1: Write failing curriculum selection tests**

Add tests that build four tracks with the production weights and assert: remediation wins, locked nodes are excluded, the most underrepresented track wins in a ten-task window, and the first incomplete node in that track is returned.

```python
def test_selector_uses_weighted_track_deficit():
    history = ["ai"] * 4 + ["backend"] * 3 + ["quality"] * 2
    selected = CurriculumSelector(CURRICULUM).select(history, completed=set())
    assert selected.track_key == "devops"

def test_selector_respects_prerequisites():
    selected = CurriculumSelector(CURRICULUM).select([], completed=set())
    assert not selected.prerequisites
```

- [ ] **Step 2: Run the new tests and verify RED**

Run: `$env:PYTHONPATH='src'; pytest tests/test_curriculum.py tests/test_task_policy.py -q`

Expected: collection fails because `domain.curriculum` and the new task fields do not exist.

- [ ] **Step 3: Implement the curriculum catalog and selector**

Define immutable `CurriculumNode`, `CurriculumTrack`, `CurriculumCatalog`, and `CurriculumSelector`. Create 48 stable nodes across `ai`, `backend`, `quality`, and `devops`, with weights `0.40`, `0.25`, `0.20`, and `0.15`; each node includes stage, prerequisites, objective, deliverable kinds, acceptance types, and radar keywords.

Selection order must be remediation, prerequisite filtering, ten-task weight deficit, catalog order, then node key. No model call is allowed in this module.

- [ ] **Step 4: Extend `TaskDraft` and policy validation**

Introduce structured task types:

```python
class TaskStep(BaseModel):
    action: str = Field(min_length=5, max_length=500)
    minutes: int = Field(ge=3, le=30)
    expected_result: str = Field(min_length=3, max_length=500)

class AcceptanceCheck(BaseModel):
    method: Literal["command", "inspection", "answer"]
    instruction: str
    expected_result: str

class RubricCriterionDraft(BaseModel):
    key: str
    label: str
    description: str
    critical: bool = False
    score_anchors: dict[str, str]
```

Add curriculum metadata, prerequisites, deliverables, acceptance checks, and remediation hint to `TaskDraft`. Validate 30–45 total step minutes, at least two acceptance checks, at least one critical criterion, score anchors `0` through `4`, and at least one source ID.

- [ ] **Step 5: Run domain tests and verify GREEN**

Run: `$env:PYTHONPATH='src'; pytest tests/test_curriculum.py tests/test_task_policy.py -q`

Expected: all curriculum and task policy tests pass.

- [ ] **Step 6: Commit Task 1**

```bash
git add services/api/src/techgrowth_api/domain services/api/tests/test_curriculum.py services/api/tests/test_task_policy.py
git commit -m "feat: add evidence-gated growth curriculum"
```

### Task 2: Backward-Compatible Task and Agent Persistence

**Files:**
- Modify: `services/api/src/techgrowth_api/models.py`
- Create: `services/api/migrations/versions/0002_curriculum_chat_radar.py`
- Modify: `services/api/src/techgrowth_api/services/growth.py`
- Modify: `services/api/src/techgrowth_api/routers/growth.py`
- Modify: `services/api/tests/test_database_schema.py`
- Modify: `services/api/tests/test_api_growth.py`

- [ ] **Step 1: Write failing persistence and API tests**

Assert that a saved task round-trips curriculum metadata, structured steps, deliverables, checks, and anchored Rubric data through `/tasks/today`. Assert that `AgentActionRecord` has `pending/executed/cancelled` status, expiry, session ownership, and JSON payload, and that `AgentRunRecord.details` defaults to `{}`.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `$env:PYTHONPATH='src'; pytest tests/test_database_schema.py tests/test_api_growth.py -q`

Expected: assertions fail because columns and serialization are missing.

- [ ] **Step 3: Add models and migration**

Add nullable/defaulted task columns so the migration is compatible with the running old image:

```python
curriculum_version = mapped_column(String(24), default="v1")
track_key = mapped_column(String(40), default="legacy")
stage_key = mapped_column(String(40), default="legacy")
node_key = mapped_column(String(120), default="legacy")
prerequisites = mapped_column(JSON, default=list)
deliverables = mapped_column(JSON, default=list)
acceptance_checks = mapped_column(JSON, default=list)
remediation_hint = mapped_column(Text, default="")
```

Add `AgentActionRecord` with `session_id`, `action_type`, `payload`, `status`, `expires_at`, and timestamps. Add `details JSON default {}` to `AgentRunRecord`. Migration `0002` must use server defaults while adding columns, backfill old rows, then retain safe defaults for mixed-version deploys.

- [ ] **Step 4: Update growth persistence and task serialization**

Make `save_draft` store every new field and make `task_dict` return stable defaults for legacy rows. Preserve the existing endpoint shape while adding fields. Map `instructions` to structured objects only for new tasks; the Web type will temporarily accept `string | TaskStep` during rollout.

- [ ] **Step 5: Run migration and focused tests**

Run:

```powershell
$env:PYTHONPATH='src'
alembic upgrade head
pytest tests/test_database_schema.py tests/test_api_growth.py -q
```

Expected: migration reaches `0002` and tests pass.

- [ ] **Step 6: Commit Task 2**

```bash
git add services/api/src/techgrowth_api/models.py services/api/migrations services/api/src/techgrowth_api/services/growth.py services/api/src/techgrowth_api/routers/growth.py services/api/tests
git commit -m "feat: persist structured learning tasks"
```

### Task 3: Curriculum-Driven Daily Task Generation

**Files:**
- Modify: `services/api/src/techgrowth_api/workflows.py`
- Modify: `services/api/src/techgrowth_api/services/growth.py`
- Modify: `services/api/src/techgrowth_api/worker.py`
- Modify: `services/api/tests/test_agent_workflows.py`
- Create: `services/api/tests/test_daily_task_generation.py`

- [ ] **Step 1: Write failing workflow tests**

Use a fixed model transport to return a detailed valid task and assert the selected curriculum node is embedded in the prompt and preserved in the result. Add failure cases for vague steps, missing checks, invalid total minutes, a fabricated source ID, and three invalid model replies followed by the curriculum-specific fallback.

- [ ] **Step 2: Run the tests and verify RED**

Run: `$env:PYTHONPATH='src'; pytest tests/test_agent_workflows.py tests/test_daily_task_generation.py -q`

Expected: failures show the workflow still accepts the old generic contract.

- [ ] **Step 3: Implement curriculum context and detailed fallback**

Change `generate_daily_task` to accept `CurriculumNode`. Build the prompt from node objective, prerequisites, deliverable/check types, latest relevant sources, and recent evidence. Reject source IDs not supplied to the model. Replace the generic fallback with a deterministic node template whose steps total 35 minutes and whose acceptance checks and 0–4 anchors satisfy policy.

- [ ] **Step 4: Select the next node from evidence and history**

Add `GrowthService.curriculum_state()` and `next_curriculum_node()` using accepted evidence plus recent non-remediation tasks. Make the Worker ask `GrowthService` for the next node before constructing the workflow. Keep `TaskPolicy` as the final gate before any database write.

- [ ] **Step 5: Run task generation tests and verify GREEN**

Run: `$env:PYTHONPATH='src'; pytest tests/test_curriculum.py tests/test_task_policy.py tests/test_agent_workflows.py tests/test_daily_task_generation.py -q`

Expected: all pass.

- [ ] **Step 6: Commit Task 3**

```bash
git add services/api/src/techgrowth_api/workflows.py services/api/src/techgrowth_api/services/growth.py services/api/src/techgrowth_api/worker.py services/api/tests
git commit -m "feat: generate curriculum-aligned daily tasks"
```

### Task 4: Observable 08:00 Radar Pipeline

**Files:**
- Create: `services/api/src/techgrowth_api/services/radar_jobs.py`
- Modify: `services/api/src/techgrowth_api/services/radar.py`
- Modify: `services/api/src/techgrowth_api/services/container.py`
- Modify: `services/api/src/techgrowth_api/integrations/radar_collector.py`
- Modify: `services/api/src/techgrowth_api/worker.py`
- Modify: `services/api/src/techgrowth_api/routers/growth.py`
- Modify: `services/api/tests/test_radar_ingestion.py`
- Modify: `services/api/tests/test_worker.py`
- Create: `services/api/tests/test_radar_jobs.py`

- [ ] **Step 1: Write failing radar job and scheduling tests**

Assert source-level results survive partial failures, a same-day successful automatic run is not duplicated, status exposes counts and sanitized errors, manual refresh shares the service, `collect-radar` uses Cron `08:00 Asia/Shanghai`, and `daily-task` uses `08:10`.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `$env:PYTHONPATH='src'; pytest tests/test_radar_ingestion.py tests/test_radar_jobs.py tests/test_worker.py -q`

Expected: missing service/status endpoint and interval-trigger mismatch failures.

- [ ] **Step 3: Return source-level collector results**

Introduce `RadarSourceResult(source_id, candidates, error)` so failures are recorded without throwing away successful sources. Strip URLs, credentials, and response bodies from persisted error messages. Keep source fetch concurrency bounded by the existing six feeds.

- [ ] **Step 4: Implement `RadarJobService`**

Use an `asyncio.Lock`, a date-based idempotency check against successful `AgentRunRecord(workflow="radar_collect")`, and one transaction for inserted items plus final run details. Call the Embedding provider separately for new candidate summaries; if one embedding fails, keep the item with a null embedding and record the count.

- [ ] **Step 5: Add status and refresh APIs**

Add `GET /radar/status` and CSRF-protected `POST /radar/refresh`. The refresh response returns run status and counts, never raw provider errors or fetched content.

- [ ] **Step 6: Change scheduler ordering**

Replace the six-hour interval with `CronTrigger(hour=8, minute=0)`. Schedule daily task for `08:10`. Store the radar job task/future so daily generation can wait up to 120 seconds for the 08:00 run, then continue with historical sources.

- [ ] **Step 7: Run radar tests and verify GREEN**

Run: `$env:PYTHONPATH='src'; pytest tests/test_radar_ingestion.py tests/test_radar_jobs.py tests/test_worker.py -q`

Expected: all pass.

- [ ] **Step 8: Commit Task 4**

```bash
git add services/api/src/techgrowth_api services/api/tests
git commit -m "feat: run observable radar collection at 0800"
```

### Task 5: Model Chat API and Intent Workflow

**Files:**
- Modify: `services/api/src/techgrowth_api/integrations/model_client.py`
- Create: `services/api/src/techgrowth_api/chat_workflow.py`
- Create: `services/api/src/techgrowth_api/services/chat_context.py`
- Modify: `services/api/src/techgrowth_api/services/container.py`
- Modify: `services/api/tests/test_model_client.py`
- Create: `services/api/tests/test_chat_workflow.py`
- Create: `services/api/tests/test_chat_context.py`

- [ ] **Step 1: Write failing natural chat and intent tests**

Assert `ModelClient.complete()` sends Chat provider URL/key/model and returns message content. Parameterize the five intents and low-confidence fallback. Verify each intent receives only its context whitelist, and a payload containing `api_key`, `totp`, `recovery`, `session`, or `private_key` is removed before prompting.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `$env:PYTHONPATH='src'; pytest tests/test_model_client.py tests/test_chat_workflow.py tests/test_chat_context.py -q`

Expected: missing `complete`, workflow, and context service failures.

- [ ] **Step 3: Implement natural completion and normalized errors**

Add `complete(system_prompt, user_prompt) -> str` using `/chat/completions`, existing Chat credentials, timeouts, and token accounting. Convert 401/403 to `provider_auth`, 429 to `provider_rate_limited`, timeouts to `provider_timeout`, invalid content to `provider_response_invalid`, and configuration absence to `provider_not_configured`.

- [ ] **Step 4: Implement whitelisted context assembly**

`ChatContextService.build(intent, page_context)` loads bounded records: today task/Rubric for coaching, latest submission/review for improvement, profile/curriculum for planning, and selected radar item for radar conversion. Serialize only named fields, tag content as untrusted, cap each collection and total text length, and recursively drop sensitive key names.

- [ ] **Step 5: Implement `ChatWorkflowService`**

Define:

```python
class ChatIntentDecision(BaseModel):
    intent: Literal["technical_qa", "task_coaching", "submission_improvement", "growth_planning", "radar_to_task"]
    confidence: float = Field(ge=0, le=1)
    needs_action: bool = False
```

Create LangGraph nodes `classify_intent`, `authorize`, `load_context`, `answer`, and `propose_action`. Confidence below `0.55` becomes `technical_qa`. Only `radar_to_task` can produce an action proposal; all other nodes are read-only.

- [ ] **Step 6: Run chat unit tests and verify GREEN**

Run: `$env:PYTHONPATH='src'; pytest tests/test_model_client.py tests/test_chat_workflow.py tests/test_chat_context.py -q`

Expected: all pass.

- [ ] **Step 7: Commit Task 5**

```bash
git add services/api/src/techgrowth_api services/api/tests
git commit -m "feat: add intent-aware tutor workflow"
```

### Task 6: Typed SSE and Confirmed Tutor Actions

**Files:**
- Modify: `services/api/src/techgrowth_api/schemas.py`
- Modify: `services/api/src/techgrowth_api/routers/system.py`
- Modify: `services/api/src/techgrowth_api/services/container.py`
- Modify: `services/api/tests/test_api_completion.py`
- Create: `services/api/tests/test_chat_actions.py`

- [ ] **Step 1: Replace the fixed-reply test with failing behavior tests**

Provide a fixed model transport and assert `/chat/stream` emits `intent`, one or more `token`, and `done` containing the model answer rather than the old sentence. Assert provider errors emit `error` then `done`. Assert `radar_to_task` emits an expiring proposal without creating a task.

- [ ] **Step 2: Run API tests and verify RED**

Run: `$env:PYTHONPATH='src'; pytest tests/test_api_completion.py tests/test_chat_actions.py -q`

Expected: the current hard-coded token response fails all new assertions.

- [ ] **Step 3: Implement SSE event serialization**

Replace the fixed `events()` body with a workflow call using provider values resolved on every request. Emit JSON payloads through a single `sse_event(name, payload)` helper. Split the completed answer into small Unicode-safe chunks for the `token` events and always terminate with `done`.

- [ ] **Step 4: Persist and confirm actions**

Persist only validated `create_task_from_radar` proposals with a 15-minute expiry and current session ID. Add `POST /chat/actions/{action_id}/confirm` and `/cancel`; lock the row, reject expired or foreign-session actions, execute at most once, and return the resulting task through `task_dict`.

- [ ] **Step 5: Run API tests and verify GREEN**

Run: `$env:PYTHONPATH='src'; pytest tests/test_api_completion.py tests/test_chat_actions.py -q`

Expected: all pass and no fixed tutor sentence remains in production code.

- [ ] **Step 6: Commit Task 6**

```bash
git add services/api/src/techgrowth_api services/api/tests
git commit -m "feat: stream tutor intents and confirmed actions"
```

### Task 7: Web Task Details, Radar Status, and Tutor UX

**Files:**
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/api.ts`
- Modify: `apps/web/src/components/Workbench.tsx`
- Modify: `apps/web/src/components/ChatDrawer.tsx`
- Modify: `apps/web/src/styles.css`
- Modify: `apps/web/src/test/App.test.tsx`
- Regenerate: `apps/web/src/generated/openapi.ts`

- [ ] **Step 1: Write failing Web tests**

Add mocked API/SSE tests asserting detailed step minutes and expected results render, deliverables/checks and anchored Rubric are visible, radar status and refresh work, intent labels render, streamed errors are shown, and an action is not executed until the confirm button is clicked.

- [ ] **Step 2: Run Web tests and verify RED**

Run: `pnpm --filter @techgrowth/web test`

Expected: missing UI labels and old `streamChat` callback signature failures.

- [ ] **Step 3: Add typed SSE consumption**

Change `streamChat` to parse event names and pass a discriminated union:

```ts
type ChatEvent =
  | { type: 'intent'; intent: ChatIntent; confidence: number }
  | { type: 'token'; text: string }
  | { type: 'action_proposal'; id: string; summary: string; expires_at: string }
  | { type: 'error'; code: string; message: string }
  | { type: 'done' }
```

Handle incomplete final buffers and malformed event JSON without crashing the drawer.

- [ ] **Step 4: Render detailed task and radar state**

Update `TodayView` to render structured steps with fixed minute badges, prerequisites, deliverables, checks, expected results, and expanded Rubric descriptions. Update `RadarView` with last run time, success/failure counts, refresh button, busy/error state, and data reload after success.

- [ ] **Step 5: Render tutor intent, errors, and confirmation**

Show a compact Chinese intent label above each assistant response. Append token events to one stable response bubble. Render action proposal confirm/cancel controls, disable them while pending, reload task/profile after confirmation, and display provider error messages inline.

- [ ] **Step 6: Regenerate OpenAPI client and run Web verification**

Run:

```powershell
pnpm openapi
pnpm --filter @techgrowth/web test
pnpm --filter @techgrowth/web lint
pnpm --filter @techgrowth/web build
```

Expected: tests, lint, and production build pass.

- [ ] **Step 7: Commit Task 7**

```bash
git add apps/web
git commit -m "feat: expose structured growth and tutor interactions"
```

### Task 8: Full Verification, Push, and Production Deployment

**Files:**
- Modify if required: `docs/deployment.md`
- Modify if required: `.env.example`

- [ ] **Step 1: Run API formatting, lint, and full tests**

Run from `services/api`:

```powershell
$env:PYTHONPATH='src'
ruff format --check src tests
ruff check src tests
pytest -q
```

Expected: formatting and lint clean; all tests pass.

- [ ] **Step 2: Run Web and Connector verification**

Run from repository root:

```powershell
pnpm --filter @techgrowth/web test
pnpm --filter @techgrowth/web lint
pnpm --filter @techgrowth/web build
Set-Location apps/connector
$env:PYTHONPATH='src'
pytest -q
```

Expected: Web tests/build and all Connector tests pass.

- [ ] **Step 3: Review security and migration behavior**

Run secret scans over the diff, inspect the migration upgrade path, verify model/provider errors contain no keys or response bodies, and confirm only `80/443` remain publicly mapped in Compose.

- [ ] **Step 4: Push the branch and main**

Push `codex/split-model-providers`, fast-forward `main` only after verification, and confirm GitHub contains the exact tested SHA.

- [ ] **Step 5: Back up and deploy to ECS**

In `/opt/techgrowth`, preserve the server-only script changes and `.env`, create a database backup, update source to the tested SHA, build API/Web images, run `alembic upgrade head`, recreate API/Web/Worker, and wait for health checks. On failure, restore previous image tags through the existing deployment script.

- [ ] **Step 6: Perform production smoke tests**

Verify public HTTPS health, real tutor response and intent label, provider error handling, detailed daily task rendering, manual radar refresh/status, next scheduler run times (`08:00` and `08:10` Asia/Shanghai), Worker health, and no duplicate task or radar run on an idempotent retry.

- [ ] **Step 7: Record final tested and deployed SHAs**

Report the exact Git commit, production URL, test totals, deployment health, and any operational follow-up that remains.

