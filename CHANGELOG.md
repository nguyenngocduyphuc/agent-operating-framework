# Changelog

## 0.3.0 (unreleased) — operational trust for no-code operators

### Added

- **Architecture & doc governance (production path):** `docs/ARCHITECTURE.md`,
  `docs/ENGINEERING_WORKFLOW.md`, `docs/DOCUMENT_GOVERNANCE.md`; `CONTRIBUTING.md`
  corrected for this repo (was a stale monorepo template). Entry map:
  `docs/INDEX.md`.
- **v0.4 F1/F2 handoff loop:** `write_session_bundle` (handoff+recap same stamp);
  write root via `nearest_repo()`; host index `$AOF_AUDIT_DIR/handoffs/index.jsonl`;
  CLI `aof resume` + MCP tool `aof_resume` (13th tool). Multirepo tests included.
- **v0.4 F3 error ledger + self-improve (propose only):** `session_log event=error`
  → `$AOF_AUDIT_DIR/errors.jsonl`; close requires `test_ref`; preflight WARNs on
  open/repeated fingerprints; CLI `aof lessons`; CLI `aof improve-check` proposes
  at most one policy change and never writes `.aof_policy.json`.
- **v0.4 F4 worker control:** `docs/WORKER_CONTROL_VI.md`; policy
  `worker_stale_after_s` (default 300) for `worker_watch` / `aof watch`.
- **CI tightened:** `.github/workflows/aof.yml` runs full `ruff check core/ tests/`,
  pytest matrix 3.10–3.12, and live `tools/list` count vs `TOOLS`.
- **Effectiveness smoke:** `scripts/effectiveness_ab_smoke.py` +
  `docs/EFFECTIVENESS_SMOKE_20260721.md` (WITH vs WITHOUT AOF on 3 failure modes;
  not a statistical bench).

- **Task lease (`core/lease.py`)**: one task, one live writer session. Repository
  identity is `git rev-parse --git-common-dir`, so every linked worktree of a repo
  shares ONE lease namespace. A second live session preflighting the same task is
  refused (`error_code -32011`) before any gate opens; a dead holder's lease is
  taken over with provenance; the lease is released on session end. Encodes the
  2026-07-20 incident: three same-day cases of two sessions trampling one branch.
- **`status_report` tool (8th MCP tool)**: plain-language session status for
  non-technical operators, Vietnamese or English (`report_language` policy key,
  `lang` argument). Four states — Blocked / Preparing / Ready / Done-with-proof —
  always ending with a concrete "next step". Deliberately never gated: a blocked
  operator most needs to see why.
- **Legacy policy compatibility**: v1 keys `require_asana_task` and
  `require_ponytail` are honoured as `require_task` / `require_karpathy` with a
  visible migration warning. Renaming a policy key must never silently disable
  enforcement (found in the 2026-07-20 audit as a live fail-open).

- **`aof init` + `aof doctor`**: zero-knowledge onboarding. `init` prepares a
  workspace (default policy + marker, idempotent, pure Python — Windows-safe).
  `doctor` health-checks the installation with REAL probes — the MCP check
  performs a live stdio handshake with a spawned server and counts all 8 tools;
  a doctor that guesses is the false-success dispatcher all over again. Plain
  vi/en output, always ending with one concrete next step. Exit 0/2.
- `docs/QUICKSTART_VI.md`: 5-minute Vietnamese quickstart for operators who do
  not know git, tests, or MCP.
- **`aof log`**: the operator's daily ledger. Digests audit.jsonl +
  decisions.jsonl into plain vi/en: sessions, done-with-proof, closed-as-blocked,
  lease collisions, failed verifications — per task, with timestamps. Honesty
  rule: reports only what the enforcement layer recorded; a Blocked is shown
  with the same prominence as a Done.
- **`aof watch`**: worker liveness by OUTPUT file mtime/size, never by "session
  alive" (the 18-minute hang of 2026-07-20 was invisible to session-based
  watchdogs). fresh/stale/missing, plain vi/en, exit 0/2.
- `docs/OPERATOR_WORKFLOW_VI.md`: the 5-step daily operating loop and the
  measured operational value table.

- **Lanes (GO-RISK-LANE, preregistered causal verdict 2026-07-16)**: the full
  chain is mandatory only on the risk lane; routine work can run lite
  (preflight + evidence). Lite is opt-in TWICE (policy `lanes_enabled` AND
  `preflight lane:"lite"`) and escalate-only: the server re-derives the git
  inventory at post_evidence and refuses lite when more than `lite_max_files`
  (default 3) changed or any `risk_globs` path was touched. A worker cannot
  talk its way into lite for risky work.
- **Wave2 canonical states in `status_report`**: Planning / Needs approval /
  Blocked / Done. `session_log` event `needs_approval` raises the
  human-in-the-loop state; `approved` or a closed evidence clears it.
- README now carries the measured claims within their preregistered honesty
  bounds: scope-block 100% vs 43% (p<0.05, replicated), pass/fabrication
  directional, +35% wall-time cost stated up front.
- `docs/REWIRE_MAP_AOF_SKILL.md`: strangler map for rewiring the live `/aof`
  skill to this core without losing any of its ~15 daily operations.

- **`aof recap`**: self-contained HTML session recap (no JS, no external assets,
  HTML-escaped) written to `docs/sessions/RECAP_<ts>.html` — per-session docs
  that update themselves. Blocked closures render as loudly as Done.
- **`aof handoff`**: markdown handoff to `docs/sessions/HANDOFF_<ts>.md` with
  Done / Blocked / Open sections and a 3-line "next session reads first" list.
- **Karpathy mode ON by default** in `aof init` policy: every contract must
  carry real Assumptions, a runnable `DoD-cmd` (re-executed by the `dod` gate),
  and a bounded Scope. The agent pays the thinking tax, never the operator.
- `docs/VONG_LAP_NO_CODE_VI.md`: the 9-step no-code loop — one prompt in, plan →
  decompose → delegate → controlled execution → conditional acceptance →
  verify → evidence → handoff → HTML recap, with per-step acceptance conditions.

- **Four report tools promoted to MCP (12 tools total)**: `op_log`,
  `session_recap`, `session_handoff`, `worker_watch`. Rationale: sandboxed
  hosts (Cowork) cannot read `~/.aof` or run host CLIs — host-side MCP tools
  make every environment equal: one server, one ledger. `aof doctor` now
  checks the tool count against the canonical TOOLS catalog dynamically —
  a hardcoded count is exactly how a stale copy answers "looks fine".

### Fixed

- Test suite no longer inherits the enclosing host workspace's `.aof_policy.json`
  when aof is vendored inside another repo (`tests/conftest.py` pins
  `AOF_WORKSPACE`).

### Noted

- `aof doctor` immediately caught a real environment defect in this repo's own
  CI habit: the suite had been running under macOS system Python 3.9 while
  `pyproject.toml` declares `requires-python >= 3.10`. Verification now runs
  under a >= 3.10 interpreter.

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
