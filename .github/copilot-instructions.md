# Exec Radar – Copilot Coding Instructions

These guidelines apply to all code contributions in this repository.
GitHub Copilot and human contributors should follow them consistently.

---

## Language and runtime

- Python **3.12+** is required.  Use `match` statements, `StrEnum`, `TypeAlias`,
  and other 3.12+ features where appropriate.
- Always include **type hints** on function signatures, class attributes, and
  return values.  Use `from __future__ import annotations` only when needed.

---

## Code style

- Format and lint with **Ruff** (`ruff check` + `ruff format`).  The project
  line length is **100** characters.
- Prefer **explicit imports** over wildcard imports (`from module import *`).
- Use **f-strings** for all string formatting.
- Favour **early returns** over deeply nested conditionals.
- Keep functions **small and focused** (single responsibility).

---

## Docstrings

- All **public** classes and functions must have a docstring.
- Use [Google-style docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).
- Document `Args:`, `Returns:`, and `Raises:` sections where relevant.
- Private helpers (`_fn`) may have a brief one-liner.

---

## Package structure

- `packages/schemas` – Pydantic v2 models only.  No business logic.
- `packages/collectors` – Source adapters; implement `BaseCollector`.
- `packages/normalizers` – Normalization logic; implement `BaseNormalizer`.
- `packages/rankers` – Scoring logic; implement `BaseRanker`.
- `packages/notifications` – Notification channels; implement `BaseNotifier`.
- `apps/api` – FastAPI app; import from packages, never the other way round.
- `apps/worker` – Async pipeline; imports from all packages.

---

## Pydantic schemas

- Always use **Pydantic v2** syntax (`model_config`, `Field`, `model_validator`).
- Add `json_schema_extra` examples to all top-level models.
- Use `StrEnum` (not `str, Enum`) for enumeration fields.
- Prefer `list[X]` and `X | None` over `List[X]` and `Optional[X]`.

---

## FastAPI conventions

- Place routes in `apps/api/app/routers/` – one file per resource.
- Use `response_model=` on every endpoint.
- Use `HTTPException` with descriptive `detail` messages.
- Write **async** route handlers; use `async def` everywhere.
- Validate query parameters with `Query(...)` and path params with `Path(...)`.

---

## Testing

- Use **pytest** for all tests.  Test files live in `tests/`.
- Name tests `test_<unit_under_test>.py` and methods `test_<what>_<expected>`.
- Prefer **unit tests** over integration tests.  Mock external dependencies.
- Use `pytest.fixture` with the narrowest possible scope.
- Assert specific values, not just that an exception was raised.

---

## Security

- **Never** hardcode secrets, API keys, or personal data in source files.
- Load all configuration from environment variables via `pydantic-settings`.
- Keep the `.env.example` file up-to-date when adding new config variables.
- Do not commit `.env` files.

---

## Adding a new collector

1. Create `packages/collectors/collectors/<name>_collector.py`.
2. Subclass `BaseCollector` and implement `source_name` and `collect()`.
3. Add a unit test in `tests/test_collectors.py`.
4. Register the collector in `apps/worker/worker.py`.

## Adding a new ranker

1. Create `packages/rankers/rankers/<name>_ranker.py`.
2. Subclass `BaseRanker` and implement `ranker_id` and `score()`.
3. Test every scoring dimension in `tests/test_ranker.py`.
