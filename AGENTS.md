# Repository Guidelines

## Project Structure & Module Organization
- `services/<domain>/` hosts microservices; Node/TypeScript variants centre on `src/`, while Python services (e.g. `services/water-simulation`) pair `src/` with `scripts/` and `docs/`.
- Shared code lives in `shared/nodejs` (`@munbon/shared`) and `shared/python`; automation helpers sit in `scripts/` and the `setup-*.sh` suite.
- Refer to `docs/` for architecture notes and root `tests/{unit,integration,e2e}` for cross-service suites; service-level tests stay beside the code.

## Build, Test, and Development Commands
- `make up` / `make up-min` start the Docker data stack; verify with `make status` and tear down with `make down`.
- `make build` produces every image, while `make build-service SERVICE=auth` and `make test` focus on one service or the Node matrix.
- Inside a Node service run `npm install`, `npm run dev`, and `npm run lint`; Python services use `poetry install` or `pip install -r requirements.txt` and usually boot with `uvicorn src.main:app --reload`.

## Coding Style & Naming Conventions
- Node/TypeScript: ESLint + Prettier (`npm run lint`, `npm run lint:fix`), 2-space indent, single quotes, semicolons, kebab-case filenames, camelCase functions.
- Run `npm run type-check` before committing; DTOs and services follow PascalCase classes with injected dependencies.
- Python 3.11: format with `poetry run black .`, lint via `poetry run ruff check .`, type-check with `poetry run mypy`; keep snake_case modules and functions.

## Testing Guidelines
- Jest covers Node suites (`npm test`, `npm run test:coverage`); name specs `*.test.ts` and isolate external calls with mocks.
- Pytest drives Python (`poetry run pytest --cov=src`) with the enforced `test_*.py` pattern.
- Always run `make test` plus any service-specific guides such as `services/water-simulation/README_TESTING.md` before a PR.

## Commit & Pull Request Guidelines
- Commits mirror history: capitalised imperative summary under ~72 characters, optional scope in parentheses, related changes only.
- PRs need a behaviour summary, affected services/scripts, test evidence, and notes on migrations, feature flags, or credentials; attach doc updates or screenshots for contract or UI changes.

## Security & Configuration Tips
- Keep secrets out of git: derive env files from `.env.example`, rotate via `setup-secrets-with-pem.sh`, remove stale keys quickly.
- Review `SECURITY_REMEDIATION_CHECKLIST.md` and `SENSOR_ENDPOINT_TOKENS.md` before shipping; clean artifacts with `remove-hardcoded-credentials.sh`.
- Use sanitised datasets in `csv_exports/` or `data_*` and document infra or credential adjustments in `docs/` for operations traceability.
