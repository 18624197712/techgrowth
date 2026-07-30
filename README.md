# TechGrowth

TechGrowth is a self-hosted, single-user technical growth agent. It turns a
curated technology radar and repository evidence into one focused daily task,
reviews the result against an explicit rubric, and maintains an evidence-backed
skill profile.

The repository contains:

- `apps/web`: React workbench.
- `services/api`: FastAPI API, worker, integrations, and PostgreSQL models.
- `apps/connector`: outbound-only Windows repository connector.
- `infra`: Caddy, production deployment, backup, and restore assets.

See `docs/deployment.md` for production setup.

## Development

Backend:

```powershell
cd services/api
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
```

Web:

```powershell
pnpm install --frozen-lockfile
pnpm --dir apps/web test
pnpm --dir apps/web dev
```

Windows connector:

```powershell
cd apps/connector
python -m pip install -e ".[dev]"
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest
python -m PyInstaller --clean --noconfirm --distpath release --workpath build connector.spec
```

Production and security details are in `docs/deployment.md`, `docs/connector.md`, and
`docs/security.md`.
