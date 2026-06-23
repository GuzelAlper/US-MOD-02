Title: feat(US-MOD-01): implement product events intake, idempotency, IN_REVIEW edit handling

Summary:
- Implemented POST /api/v1/b2b/events to accept product events from B2B.
- Added idempotency handling: store `IdempotencyKey` and treat duplicate keys as no-op (HTTP 200).
- Implemented snapshot storage on `ProductCard`: `json_before` and `json_after`.
- Edited behavior: if card is `IN_REVIEW`, edits update fields but keep status; if `MODERATED`/`BLOCKED`, edits move card back to `PENDING`.
- Added tests covering happy/unhappy flows and `edited_updates_in_review`.
- Added ADR: docs/adr/0001-idempotency-and-snapshots.md

Files changed (high level):
- app/services/product_service.py
- app/api/v1/endpoints/events.py
- app/schemas/event.py
- app/models/product_card.py
- tests/test_product_events.py
- docs/adr/0001-idempotency-and-snapshots.md
- .gitignore

Test run (local):
```
5 passed, 3 warnings
```

ADR summary:
- Chosen snapshot format: `json_before` + `json_after` (easier diagnostics, moderate storage cost).
- Duplicate events handled by storing idempotency key and returning 200 on duplicate.

Notes for reviewers / deployment:
- `.venv` and `test.db` were accidentally staged earlier and removed in a cleanup commit; check commit history if needed.
- If you want a clean history without the accidental files, we can squash/rebase before merging.
- No DB migrations required (SQLite models updated in-place). If you use a production DB, create migration.

How to test locally:
- Create and activate a Python venv, install requirements from `requirements.txt`.
- Run tests: `pytest -q`

Link to open PR (created branch): https://github.com/GuzelAlper/neomarket-moderation-service/pull/new/feature/US-MOD-01

