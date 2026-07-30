# Split Model Provider Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let TechGrowth use independent OpenAI-compatible base URLs, model names, and encrypted API keys for chat and embeddings while preserving legacy configuration.

**Architecture:** Store two explicit provider groups in the existing key-value settings table, resolve every field through a backward-compatible precedence function, and route chat and embedding calls through separate HTTP client configuration. Update the setup API and React form to expose the two groups without returning secrets.

**Tech Stack:** FastAPI, Pydantic Settings, SQLAlchemy, httpx, pytest, React 19, TypeScript, Vitest, Testing Library, Docker Compose.

---

### Task 1: Independent Encrypted Provider Settings

**Files:**
- Modify: `services/api/src/techgrowth_api/services/settings.py`
- Modify: `services/api/src/techgrowth_api/routers/settings.py`
- Modify: `services/api/tests/test_settings_service.py`
- Modify: `services/api/tests/test_api_settings.py`

- [ ] **Step 1: Write failing service tests**

Add tests that save this payload and assert independent masked status values:

```python
ProviderSettings(
    chat={
        "base_url": "https://chat.example/v1",
        "model": "chat-model",
        "api_key": "chat-secret",
    },
    embedding={
        "base_url": "https://embed.example/v1",
        "model": "embed-model",
        "api_key": "embed-secret",
    },
)
```

Assert `provider_status()` returns nested `chat` and `embedding` objects with
their URL, model, and `api_key_configured=True`, and assert neither secret is
present in the serialized status or raw database rows.

Add a second test that saves an empty API key for each already-configured
provider and proves both previous encrypted keys remain unchanged.

Add a third test that attempts the first save with an empty key and asserts the
service rejects that provider with a capability-specific validation error.

- [ ] **Step 2: Verify the service tests fail for the missing nested contract**

Run:

```powershell
cd services/api
python -m pytest tests/test_settings_service.py -q
```

Expected: FAIL because `ProviderSettings` does not accept `chat` and
`embedding` groups and status is still flat.

- [ ] **Step 3: Implement the nested settings model and storage**

Introduce these models:

```python
class ProviderEndpointSettings(BaseModel):
    base_url: HttpUrl
    model: str = Field(min_length=1)
    api_key: str = ""


class ProviderSettings(BaseModel):
    chat: ProviderEndpointSettings
    embedding: ProviderEndpointSettings
```

Store keys under `provider.chat.*` and `provider.embedding.*`. When an incoming
`api_key` is empty, skip updating that key if a stored value already exists.
Return only `base_url`, `model`, and `api_key_configured` from public status.
If a provider has neither an incoming key nor a stored key, raise a dedicated
settings validation exception; translate it to HTTP 422 in the settings router.

- [ ] **Step 4: Update and run the setup API contract test**

Send the nested payload to `PUT /api/v1/setup/provider`, then assert
`GET /api/v1/setup` returns both groups and contains neither secret.

Run:

```powershell
python -m pytest tests/test_settings_service.py tests/test_api_settings.py -q
```

Expected: all tests PASS.

- [ ] **Step 5: Commit encrypted settings support**

```powershell
git add services/api/src/techgrowth_api/services/settings.py services/api/src/techgrowth_api/routers/settings.py services/api/tests/test_settings_service.py services/api/tests/test_api_settings.py
git commit -m "feat: split encrypted model provider settings"
```

### Task 2: Backward-Compatible Runtime Resolution

**Files:**
- Modify: `services/api/src/techgrowth_api/config.py`
- Modify: `services/api/src/techgrowth_api/worker.py`
- Create: `services/api/tests/test_provider_resolution.py`

- [ ] **Step 1: Write failing precedence tests**

Define tests for a new pure function `resolve_provider_settings(settings,
stored)` that assert each field follows this order:

```python
stored provider-specific value
stored legacy value
provider-specific environment-backed Settings value
legacy environment-backed Settings value
```

Test partial configuration field by field, including a new chat URL combined
with a legacy key and a legacy embedding model.

- [ ] **Step 2: Verify resolution tests fail**

Run:

```powershell
cd services/api
python -m pytest tests/test_provider_resolution.py -q
```

Expected: FAIL because the provider-specific Settings fields and resolver do
not exist.

- [ ] **Step 3: Add provider-specific environment settings**

Add these optional fields to `Settings`:

```python
chat_base_url: str = ""
chat_api_key: str = ""
embedding_base_url: str = ""
embedding_api_key: str = ""
```

Keep existing `chat_model`, `embedding_model`, `openai_base_url`, and
`openai_api_key` fields as legacy-compatible inputs.

- [ ] **Step 4: Implement and use the resolver**

Create a pure resolver in `worker.py` that returns a copied `Settings` with
resolved chat and embedding fields. Make `daily_task()` call the resolver
instead of assigning one shared base URL and key.

- [ ] **Step 5: Run resolution and scheduler tests**

```powershell
python -m pytest tests/test_provider_resolution.py tests/test_worker.py -q
```

Expected: all tests PASS.

- [ ] **Step 6: Commit runtime resolution**

```powershell
git add services/api/src/techgrowth_api/config.py services/api/src/techgrowth_api/worker.py services/api/tests/test_provider_resolution.py
git commit -m "feat: resolve independent model providers"
```

### Task 3: Route Requests Through Separate Credentials

**Files:**
- Modify: `services/api/src/techgrowth_api/integrations/model_client.py`
- Modify: `services/api/tests/test_model_client.py`
- Modify: `services/api/src/techgrowth_api/evaluation.py`

- [ ] **Step 1: Write failing request-routing tests**

Add one test that executes both methods with these settings:

```python
Settings(
    chat_base_url="https://chat.example/v1",
    chat_api_key="chat-secret",
    chat_model="chat-model",
    embedding_base_url="https://embed.example/v1",
    embedding_api_key="embed-secret",
    embedding_model="embed-model",
)
```

Record requests in an `httpx.MockTransport` handler and assert:

```python
requests[0].url == "https://chat.example/v1/chat/completions"
requests[0].headers["authorization"] == "Bearer chat-secret"
requests[1].url == "https://embed.example/v1/embeddings"
requests[1].headers["authorization"] == "Bearer embed-secret"
```

Add capability-specific missing-configuration tests for both methods.

- [ ] **Step 2: Verify routing tests fail for shared credentials**

```powershell
cd services/api
python -m pytest tests/test_model_client.py -q
```

Expected: FAIL because embedding still uses the legacy shared URL and key.

- [ ] **Step 3: Implement separate chat and embedding clients**

Make `configured` represent chat readiness. Add `embedding_configured` for the
embedding triplet. `structured()` uses only chat fields; `embedding()` uses
only embedding fields. Preserve token accounting and all existing retry/schema
validation behavior.

Resolve direct-client compatibility at the access point: chat uses
`chat_base_url or openai_base_url` and `chat_api_key or openai_api_key`;
embedding uses `embedding_base_url or openai_base_url` and
`embedding_api_key or openai_api_key`. This keeps existing CLI and evaluation
callers compatible even when they do not pass through the worker resolver.

- [ ] **Step 4: Update real-model evaluation validation**

Require only resolved chat configuration for chat-only evaluation. Accept both
provider-specific and legacy environment values by using the same fallback
properties as the model client.

- [ ] **Step 5: Run model and evaluation tests**

```powershell
python -m pytest tests/test_model_client.py tests/test_evaluation.py -q
```

Expected: all tests PASS.

- [ ] **Step 6: Commit request routing**

```powershell
git add services/api/src/techgrowth_api/integrations/model_client.py services/api/src/techgrowth_api/evaluation.py services/api/tests/test_model_client.py
git commit -m "feat: route chat and embeddings independently"
```

### Task 4: Split the Web Settings Form

**Files:**
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/components/Workbench.tsx`
- Modify: `apps/web/src/test/App.test.tsx`
- Modify: `apps/web/src/generated/openapi.ts`

- [ ] **Step 1: Write a failing frontend test**

Return this setup response from the fetch mock:

```typescript
provider: {
  chat: { base_url: 'https://chat.example/v1', model: 'chat-model', api_key_configured: true },
  embedding: { base_url: 'https://embed.example/v1', model: 'embed-model', api_key_configured: false },
}
```

Navigate to settings and assert separate headings, URL inputs, model inputs,
and password inputs exist. Submit the form and assert the request body contains
separate `chat` and `embedding` objects.

- [ ] **Step 2: Verify the frontend test fails**

```powershell
pnpm --dir apps/web test -- App.test.tsx
```

Expected: FAIL because the form still renders one shared provider group.

- [ ] **Step 3: Update types and the settings form**

Change `SetupStatus.provider` to:

```typescript
provider: {
  chat: ProviderEndpointStatus
  embedding: ProviderEndpointStatus
}
```

Render two field groups and submit:

```typescript
{
  chat: { base_url, model, api_key },
  embedding: { base_url, model, api_key },
}
```

Use independent configured-key placeholders and update the topbar status to
show complete or partial model configuration.

- [ ] **Step 4: Regenerate the OpenAPI TypeScript file**

Start the API with the test configuration, then run:

```powershell
pnpm --dir apps/web generate:api
```

Stop the temporary API process after generation.

- [ ] **Step 5: Run web verification**

```powershell
pnpm --dir apps/web test
pnpm --dir apps/web lint
pnpm --dir apps/web build
```

Expected: all tests PASS, lint reports no errors, and TypeScript/Vite build
completes.

- [ ] **Step 6: Commit the web contract**

```powershell
git add apps/web/src/types.ts apps/web/src/components/Workbench.tsx apps/web/src/test/App.test.tsx apps/web/src/generated/openapi.ts
git commit -m "feat: configure chat and embeddings separately"
```

### Task 5: Documentation, Full Verification, Push, And Deployment

**Files:**
- Modify: `.env.example`
- Modify: `docs/deployment.md`
- Modify: `README.md`

- [ ] **Step 1: Document the six provider-specific variables**

Add the new Chat and Embedding Base URL/API Key/model variables to
`.env.example`. Mark `TG_OPENAI_BASE_URL` and `TG_OPENAI_API_KEY` as legacy
fallbacks in deployment documentation. Explain that both configured Base URLs
must include `/v1`.

- [ ] **Step 2: Run the complete local verification suite**

```powershell
cd services/api
python -m ruff check .
python -m pytest -q
cd ../..
pnpm --dir apps/web test
pnpm --dir apps/web lint
pnpm --dir apps/web build
cd apps/connector
python -m pytest -q
```

Expected: Ruff exits 0; all API, web, and connector tests pass; the web build
exits 0.

- [ ] **Step 3: Commit documentation and push**

```powershell
git add .env.example docs/deployment.md README.md
git commit -m "docs: explain split model provider configuration"
git push origin codex/techgrowth-v1
git push origin codex/techgrowth-v1:main
```

- [ ] **Step 4: Deploy the verified commit to ECS**

Through Alibaba Cloud Command Assistant, fetch the pushed commit in
`/opt/techgrowth`, rebuild API and Web images with the already configured
Docker/PyPI mirrors, run Alembic, and restart Compose without exposing database
ports. Preserve the existing `.env` secrets.

- [ ] **Step 5: Verify production**

Confirm all Compose services are running and API/Web/database health checks are
healthy. Verify `https://www.hy20250221.online/api/v1/health`, sign in, save two
different provider configurations, and confirm test requests carry the correct
provider-specific Authorization header without logging either key.
