# 0001 - Idempotency storage and snapshot format

Context:
- Moderation service receives product events from B2B. Events can be retried by the sender and network may deliver duplicates.

Decision:
- Store an `IdempotencyKey` (key, product_id, event_type, processed_at) for each processed event. On receiving an event with an already-seen key, do not apply side effects and return HTTP 200.
- Store `json_before` and `json_after` on `ProductCard` (two snapshots).

Rationale:
- Alternatives considered:
  1. `json_before` + `json_after` snapshots (chosen)
  2. Full snapshot only (only `json_after`)
  3. Delta (store only the diff)
- Chosen because: (a) two snapshots make incident diagnosis straightforward (moderator can immediately see before/after), (b) implementation complexity is low, (c) storage overhead is acceptable for Moderate scale. Delta is compact but harder to inspect and requires additional reconstruction logic; full-only loses prior state for quick diagnostics.

Consequences:
- Duplicate events are idempotent by key and are acknowledged with 200 without changing state.
- Moderators can inspect `json_before`/`json_after` to understand edits.

