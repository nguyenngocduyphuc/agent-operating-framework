# Changelog

## 0.2.0b2 (unreleased)

### Breaking

- **Default audit directory moved from `~/.npflight/` to `~/.aof/`.**
  Both `audit.jsonl` and the new `decisions.jsonl` now live under `~/.aof/`.
  Existing logs are **not** migrated automatically. To keep the previous
  location, set `AOF_AUDIT_DIR=~/.npflight`. If you have tooling that reads
  `~/.npflight/audit.jsonl`, either repoint it or set that env var before
  upgrading.

### Added

- `core/enforcement.py`: decision records (`decisions.jsonl`) and stall
  detection. Contract checks, gate verdicts, and posted evidence now leave a
  durable decision trail alongside the audit log.
- Stall detection warns when one operation fails repeatedly in a single session
  (default 5). It **warns only and never blocks** — blocking a repeated failure
  would also block the retry that fixes it.
- `verify_gate` accepts `timeout_s` (default 120s, ceiling 1800s) and applies it
  to each command. Previously the 120s timeout was hardcoded and unreachable by
  callers, so slow suites could not pass.

### Fixed

- `verify_gate`'s `"required": ["gate_type"]` sat outside `inputSchema`, so the
  required argument was never advertised to clients. Moved inside the schema.
- `session_log` required both `event` and `data`; `data` is now optional, which
  matches how the tool is actually called.
- `audit_scope.scope` stays an array (a glob may contain a comma, which a
  delimited string cannot express) but a comma/newline separated string is now
  coerced for backward compatibility with older clients.

### Note on enforcement

The precondition chain (preflight → contract → verify_gate → audit_scope →
post_evidence) remains **always on** and is enforced at the JSON-RPC error
layer. It is deliberately not configurable: a refusal must not be returned as a
success payload carrying a false flag, because a naive client can mistake that
for a result.
