---
status: accepted
---

# Two run modes: Owner-only Mode on SQLite, multi-user on PostgreSQL

The multi-user deployment needs an always-on process (web UI, Telegram and Discord bots, per-Member Schedules), so it runs as Docker Compose on a VPS with PostgreSQL to avoid the SQLite write contention that upstream already works around (WAL plus "database is locked" retries) even single-user. We keep upstream's GitHub Actions, Desktop and local deployments as an Owner-only Mode with no Members, still on SQLite, because PostgreSQL is impractical there.

## Consequences

Storage stays behind upstream's SQLAlchemy layer and must work on both engines, and CI runs the test suite against both. Every Member-aware feature needs a defined behaviour in Owner-only Mode, where the Owner is effectively the only Member.
