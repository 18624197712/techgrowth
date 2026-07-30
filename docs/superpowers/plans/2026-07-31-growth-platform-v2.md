# TechGrowth Growth Platform v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver selectable beginner-to-architect technology tracks, comprehensive regenerable tasks, controlled tutor Function Calling, an analytics dashboard, domestic radar sources, reliable repository matching, GitHub import, and a usable resizable tutor, then publish and deploy the tested SHA.

**Architecture:** Extend the existing FastAPI modular monolith with focused curriculum, task, tool, analytics, radar-source, repository-identity, and GitHub services. Preserve evidence-gated progress and confirmed writes; expose additive APIs and backward-compatible migrations to the React workbench and outbound-only Windows connector.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, LangGraph, httpx, PostgreSQL/pgvector, React, TypeScript, Vitest, Testing Library, PySide6, pytest, Docker Compose, Caddy.

**Execution note:** The repository owner selected inline execution by the current primary agent. Do not delegate and do not use Coze.

---

### Task 1: Curriculum v2 and Active Track State

**Files:**
- Modify: `services/api/src/techgrowth_api/domain/curriculum.py`
- Modify: `services/api/src/techgrowth_api/models.py`
- Create: `services/api/migrations/versions/0003_growth_platform_v2.py`
- Create: `services/api/src/techgrowth_api/services/curriculum.py`
- Modify: `services/api/src/techgrowth_api/services/container.py`
- Modify: `services/api/src/techgrowth_api/routers/growth.py`
- Create: `services/api/tests/test_curriculum_v2.py`
- Create: `services/api/tests/test_api_curriculum.py`

- [ ] **Step 1: Write failing curriculum tests**

Assert that the catalog contains `java`, `python_ai`, `go`, `node_ts`, and `algorithms`, each with four ordered stages. Assert exactly one primary track is active, switching preserves completed nodes, and algorithm frequency accepts `0..7`.

```python
def test_catalog_exposes_selectable_tracks():
    assert [track.key for track in CURRICULUM.tracks] == [
        "java", "python_ai", "go", "node_ts", "algorithms"
    ]
    assert all({node.stage_key for node in track.nodes} == {
        "foundation", "practice", "production", "architecture"
    } for track in CURRICULUM.tracks)
```

- [ ] **Step 2: Verify RED**

Run: `$env:PYTHONPATH='src'; pytest tests/test_curriculum_v2.py tests/test_api_curriculum.py -q`

Expected: failures because v2 track keys, persistence, and `/curriculum` APIs do not exist.

- [ ] **Step 3: Implement catalog and state**

Add 12 stable nodes to each main track and at least 24 algorithm nodes. Add `CurriculumStateRecord(active_track_key, algorithm_days_per_week, catalog_version, updated_at)` and `CurriculumService` methods:

```python
def state(self) -> CurriculumState: ...
def switch_track(self, track_key: str) -> CurriculumState: ...
def set_algorithm_frequency(self, days_per_week: int) -> CurriculumState: ...
def progress(self) -> list[TrackProgress]: ...
def next_node(self, on_date: date) -> CurriculumNode: ...
```

Expose `GET /curriculum`, `PUT /curriculum/active-track`, and `PUT /curriculum/algorithm-frequency`, all writes protected by CSRF.

- [ ] **Step 4: Verify GREEN and migrate a test database**

Run: `$env:PYTHONPATH='src'; alembic upgrade head; pytest tests/test_curriculum_v2.py tests/test_api_curriculum.py -q`

Expected: migration reaches `0003`; focused tests pass.

- [ ] **Step 5: Commit**

```powershell
git add services/api/src/techgrowth_api/domain/curriculum.py services/api/src/techgrowth_api/models.py services/api/migrations services/api/src/techgrowth_api/services/curriculum.py services/api/src/techgrowth_api/services/container.py services/api/src/techgrowth_api/routers/growth.py services/api/tests/test_curriculum_v2.py services/api/tests/test_api_curriculum.py
git commit -m "feat: add selectable growth tracks"
```

### Task 2: Comprehensive Tasks, Regeneration, and Hints

**Files:**
- Modify: `services/api/src/techgrowth_api/domain/tasks.py`
- Modify: `services/api/src/techgrowth_api/models.py`
- Modify: `services/api/migrations/versions/0003_growth_platform_v2.py`
- Modify: `services/api/src/techgrowth_api/workflows.py`
- Modify: `services/api/src/techgrowth_api/services/daily_tasks.py`
- Modify: `services/api/src/techgrowth_api/routers/growth.py`
- Modify: `services/api/src/techgrowth_api/schemas.py`
- Create: `services/api/tests/test_task_v2.py`
- Create: `services/api/tests/test_task_regeneration.py`

- [ ] **Step 1: Write failing contract and regeneration tests**

Build a `TaskDraft` with theory, explicit problem, constraints, three hint levels, and a solution outline. Assert vague problem statements fail, hints remain hidden by default, regeneration replaces only an unsubmitted task, failure preserves the old task, and an idempotency key returns the same replacement.

```python
def test_regeneration_preserves_old_task_when_generation_fails(client, task):
    response = client.post(
        f"/api/v1/tasks/{task.id}/regenerate",
        headers={"Idempotency-Key": "regen-1"},
        json={"reason": "题目不够明确"},
    )
    assert response.status_code == 502
    assert load_task(task.id).status == "open"
```

- [ ] **Step 2: Verify RED**

Run: `$env:PYTHONPATH='src'; pytest tests/test_task_v2.py tests/test_task_regeneration.py -q`

Expected: missing task fields and routes fail.

- [ ] **Step 3: Implement task v2**

Add `task_kind`, `learning_objectives`, `theory_brief`, `problem_statement`, `constraints`, `starter_context`, `hints`, `revealed_hint_level`, `solution_outline`, `solution_revealed_at`, `replaced_task_id`, and `regeneration_reason`. Extend prompt and deterministic fallback with all required sections and retain 30–45 minute policy.

Expose:

```text
POST /tasks/{task_id}/regenerate
POST /tasks/{task_id}/hints/{level}/reveal
POST /tasks/{task_id}/solution/reveal
```

Regeneration uses a row lock and idempotency record, generates before mutating the old row, then atomically marks old `replaced` and inserts new `open` task.

- [ ] **Step 4: Verify GREEN**

Run: `$env:PYTHONPATH='src'; pytest tests/test_task_policy.py tests/test_agent_workflows.py tests/test_task_v2.py tests/test_task_regeneration.py -q`

Expected: all task and workflow tests pass.

- [ ] **Step 5: Commit**

```powershell
git add services/api
git commit -m "feat: generate comprehensive regenerable tasks"
```

### Task 3: Tutor Tool Registry and Function Calling

**Files:**
- Create: `services/api/src/techgrowth_api/tools.py`
- Modify: `services/api/src/techgrowth_api/integrations/model_client.py`
- Modify: `services/api/src/techgrowth_api/chat_workflow.py`
- Modify: `services/api/src/techgrowth_api/services/chat_actions.py`
- Modify: `services/api/src/techgrowth_api/services/container.py`
- Modify: `services/api/src/techgrowth_api/routers/system.py`
- Create: `services/api/tests/test_tool_registry.py`
- Modify: `services/api/tests/test_chat_workflow.py`
- Modify: `services/api/tests/test_chat_actions.py`

- [ ] **Step 1: Write failing tool tests**

Assert all eleven approved tool names are registered, unknown tools are rejected, read tools execute without proposals, write tools create session-bound confirmations, sensitive keys are stripped, and a chat turn cannot exceed three tool rounds.

```python
def test_write_tool_requires_confirmation(registry):
    result = registry.prepare("switch_primary_track", {"track_key": "go"}, context)
    assert result.kind == "proposal"
    assert curriculum.state().active_track_key != "go"
```

- [ ] **Step 2: Verify RED**

Run: `$env:PYTHONPATH='src'; pytest tests/test_tool_registry.py tests/test_chat_workflow.py tests/test_chat_actions.py -q`

Expected: registry and generic tool events are missing.

- [ ] **Step 3: Implement registry and model protocol**

Define `ToolSpec(name, description, arguments_model, result_model, write, execute)` and register the approved tools. Extend `ModelClient` to send OpenAI-compatible `tools` and parse `tool_calls`; fall back to a Pydantic `ToolDecision` only when the provider rejects native tools. Emit `tool_call`, `tool_result`, `action_proposal`, `token`, `error`, and `done` SSE events.

- [ ] **Step 4: Verify GREEN**

Run: `$env:PYTHONPATH='src'; pytest tests/test_model_client.py tests/test_tool_registry.py tests/test_chat_workflow.py tests/test_chat_actions.py tests/test_api_completion.py -q`

Expected: all chat and tool tests pass.

- [ ] **Step 5: Commit**

```powershell
git add services/api
git commit -m "feat: add controlled tutor function calling"
```

### Task 4: Analytics APIs and Data Platform Web View

**Files:**
- Create: `services/api/src/techgrowth_api/services/analytics.py`
- Create: `services/api/src/techgrowth_api/routers/analytics.py`
- Modify: `services/api/src/techgrowth_api/main.py`
- Modify: `services/api/src/techgrowth_api/services/container.py`
- Create: `services/api/tests/test_analytics.py`
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/api.ts`
- Modify: `apps/web/src/components/Workbench.tsx`
- Create: `apps/web/src/components/DataPlatform.tsx`
- Create: `apps/web/src/components/CurriculumCenter.tsx`
- Modify: `apps/web/src/styles.css`
- Modify: `apps/web/src/test/App.test.tsx`

- [ ] **Step 1: Write failing API and Web tests**

Assert `/analytics/overview?range=30d` returns definitions and components for learning minutes, pass rate, route progress, radar engagement, repository facts, and AI success. Assert Web navigation opens unified overview and drills into learning, radar, repositories, and AI views.

- [ ] **Step 2: Verify RED**

Run:

```powershell
Set-Location services/api
$env:PYTHONPATH='src'
pytest tests/test_analytics.py -q
Set-Location ../../
pnpm --filter @techgrowth/web test -- --run
```

Expected: missing analytics routes and views fail.

- [ ] **Step 3: Implement analytics and Web views**

Create aggregate queries for `7d`, `30d`, `90d`, and `all`. Every metric response includes `key`, `label`, `value`, `unit`, `definition`, and `components`. Build an unframed operational dashboard with a compact metric row, stage progress, trend charts, tables, and the approved drill-down tabs. Add curriculum selection and algorithm frequency controls.

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
Set-Location services/api
$env:PYTHONPATH='src'
pytest tests/test_analytics.py tests/test_api_curriculum.py -q
Set-Location ../../
pnpm --filter @techgrowth/web test -- --run
pnpm --filter @techgrowth/web lint
```

Expected: API and Web focused suites pass.

- [ ] **Step 5: Commit**

```powershell
git add services/api apps/web
git commit -m "feat: add growth data platform"
```

### Task 5: Domestic Radar Registry and Dynamic Health

**Files:**
- Modify: `services/api/src/techgrowth_api/integrations/radar_sources.py`
- Modify: `services/api/src/techgrowth_api/integrations/radar_collector.py`
- Modify: `services/api/src/techgrowth_api/services/radar_jobs.py`
- Modify: `services/api/src/techgrowth_api/routers/growth.py`
- Modify: `services/api/tests/test_radar_ingestion.py`
- Modify: `services/api/tests/test_radar_jobs.py`
- Modify: `apps/web/src/components/Workbench.tsx`

- [ ] **Step 1: Write failing source registry tests**

Assert the registry contains domestic and international regions, domestic sources bypass `TG_OUTBOUND_PROXY_URL`, source totals are dynamic, public feed fixtures parse, and one source failure does not fail the run.

- [ ] **Step 2: Verify RED**

Run: `$env:PYTHONPATH='src'; pytest tests/test_radar_ingestion.py tests/test_radar_jobs.py -q`

Expected: region routing and dynamic source totals are missing.

- [ ] **Step 3: Implement verified sources and health**

Add stable public feeds for InfoQ Chinese, OSChina, SegmentFault, V2EX technology, Ruan Yifeng, and verified developer feeds that pass fixture and live URL validation. Add `region` and `enabled` to source definitions, direct transport for domestic feeds, proxy transport for international feeds, and `total_sources` in status. Replace Web `/6` with the API total.

- [ ] **Step 4: Verify GREEN**

Run: `$env:PYTHONPATH='src'; pytest tests/test_radar_ingestion.py tests/test_radar_jobs.py tests/test_worker.py -q`

Expected: radar tests pass with partial failure isolation.

- [ ] **Step 5: Commit**

```powershell
git add services/api apps/web
git commit -m "feat: expand domestic technology radar"
```

### Task 6: Repository Identity, GitHub Import, and Connector Diagnostics

**Files:**
- Create: `services/api/src/techgrowth_api/domain/repositories.py`
- Modify: `services/api/src/techgrowth_api/models.py`
- Modify: `services/api/migrations/versions/0003_growth_platform_v2.py`
- Modify: `services/api/src/techgrowth_api/integrations/github.py`
- Create: `services/api/src/techgrowth_api/services/repositories.py`
- Modify: `services/api/src/techgrowth_api/routers/connector.py`
- Modify: `services/api/src/techgrowth_api/routers/settings.py`
- Create: `services/api/tests/test_repository_identity.py`
- Create: `services/api/tests/test_github_import.py`
- Modify: `apps/connector/src/techgrowth_connector/client.py`
- Modify: `apps/connector/src/techgrowth_connector/tray.py`
- Create: `apps/connector/tests/test_connection_diagnostics.py`
- Modify: `apps/web/src/components/Workbench.tsx`

- [ ] **Step 1: Write failing identity and diagnostic tests**

Assert SSH and HTTPS GitHub remotes normalize to the same identity, unique remotes auto-match, ambiguous paths require confirmation, GitHub PAT never appears in responses, and connector diagnostics classify Alibaba ICP 403 and TLS EOF/reset separately.

```python
@pytest.mark.parametrize("remote", [
    "git@github.com:Owner/Repo.git",
    "ssh://git@github.com/Owner/Repo.git",
    "https://github.com/Owner/Repo/",
])
def test_canonical_remote(remote):
    assert canonical_remote_url(remote) == "github.com/owner/repo"
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
Set-Location services/api
$env:PYTHONPATH='src'
pytest tests/test_repository_identity.py tests/test_github_import.py -q
Set-Location ../../apps/connector
$env:PYTHONPATH='src'
pytest tests/test_connection_diagnostics.py -q
```

Expected: canonical identity, GitHub routes, and diagnostic mapping are missing.

- [ ] **Step 3: Implement repository and GitHub services**

Normalize remotes, add provider/stable ID and match status, merge connector and GitHub observations, and expose list/import/match/sync APIs. Store Fine-grained PAT through encrypted provider settings, validate read-only repository access before saving, and redact all token-bearing errors.

- [ ] **Step 4: Implement connector preflight**

Add `diagnose_server(url) -> ConnectionDiagnostic` that performs URL, DNS, TLS/HTTP, and `/health` checks without weakening verification. Map known response bodies and socket failures to stable Chinese messages. Surface the diagnostic before pairing in the tray dialog.

- [ ] **Step 5: Verify GREEN**

Run focused API and connector suites from Step 2. Expected: all pass.

- [ ] **Step 6: Commit**

```powershell
git add services/api apps/connector apps/web
git commit -m "feat: connect and diagnose code repositories"
```

### Task 7: Task UI, Generic Tool UX, and Resizable Tutor

**Files:**
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/api.ts`
- Modify: `apps/web/src/components/Workbench.tsx`
- Modify: `apps/web/src/components/ChatDrawer.tsx`
- Modify: `apps/web/src/styles.css`
- Modify: `apps/web/src/test/App.test.tsx`
- Create: `apps/web/src/test/ChatDrawer.test.tsx`

- [ ] **Step 1: Write failing Web interaction tests**

Assert all task sections render, regenerate confirms and preserves the old task while loading, hints reveal by level, generic tool proposals confirm/cancel, chat text uses the accessibility class, drawer width persists, clamps to 320–720px, keyboard resizing works, and mobile drawer ignores stored width.

- [ ] **Step 2: Verify RED**

Run: `pnpm --filter @techgrowth/web test -- --run`

Expected: task v2 controls, generic events, and resize handle are missing.

- [ ] **Step 3: Implement interactions**

Render theory, problem, constraints, steps, deliverables, checks, Rubric, tiered hints, and post-submit solution. Parse generic `tool_call/tool_result/action_proposal` SSE events. Add an accessible separator resize handle using pointer capture and arrow keys, store `techgrowth.chat.width`, and apply the width only above the mobile breakpoint. Set chat body to 15px.

- [ ] **Step 4: Verify GREEN and build**

Run:

```powershell
pnpm --filter @techgrowth/web test -- --run
pnpm --filter @techgrowth/web lint
pnpm --filter @techgrowth/web build
```

Expected: all Web tests, lint, and build pass.

- [ ] **Step 5: Commit**

```powershell
git add apps/web
git commit -m "feat: improve daily task and tutor workspace"
```

### Task 8: Full Verification, GitHub Publication, and ECS Deployment

**Files:**
- Modify if required: `.env.example`
- Modify if required: `docs/deployment.md`
- Modify if required: `docs/connector.md`

- [ ] **Step 1: Run full API verification**

Run from `services/api`:

```powershell
$env:PYTHONPATH='src'
ruff format --check src tests
ruff check src tests
pytest -q
```

Expected: formatting and lint clean; zero failed tests.

- [ ] **Step 2: Run full Web and Connector verification**

Run from repository root:

```powershell
pnpm --filter @techgrowth/web test -- --run
pnpm --filter @techgrowth/web lint
pnpm --filter @techgrowth/web build
Set-Location apps/connector
$env:PYTHONPATH='src'
pytest -q
```

Expected: zero failed tests and a successful production build.

- [ ] **Step 3: Validate migration, secrets, and production assets**

Upgrade a clean database and an existing schema snapshot to head. Search tracked files and the staged diff for private keys, bearer tokens, API keys, and real PATs. Validate Docker Compose and Caddy configuration without exposing database ports.

- [ ] **Step 4: Push tested commits to GitHub**

Push `codex/split-model-providers`, fast-forward `main` after verification, push `main`, and confirm GitHub resolves the tested SHA.

- [ ] **Step 5: Resolve public HTTPS prerequisite**

Run fresh `curl` and Python/httpx checks against `https://www.hy20250221.online/api/v1/health`. If Alibaba still returns `Non-compliance ICP Filing` on HTTP or resets TLS, use the signed-in Alibaba console only for read-only diagnosis and permitted configuration changes; do not weaken TLS. Continue server deployment through SSH when available, but record that connector/public smoke tests remain externally blocked until备案接入生效.

- [ ] **Step 6: Back up and deploy the tested SHA**

In `/opt/techgrowth`, back up PostgreSQL, preserve `.env`, pull the tested SHA, build or pull SHA-tagged images, run `alembic upgrade head`, recreate API/Web/Worker, and wait for health checks. Roll back to the prior SHA if health checks fail.

- [ ] **Step 7: Run production smoke tests**

Verify container health, migration head, authenticated route behavior, curriculum APIs, task regeneration, analytics, radar dynamic source total, chat tool protocol, GitHub settings redaction, and connector diagnostic response. Report exact local/GitHub/deployed SHA and any Alibaba external-access limitation with command evidence.
