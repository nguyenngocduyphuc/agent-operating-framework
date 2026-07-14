# AntiGravity-IDE Upgrade — Structure Rules

> **AI agents: READ THIS before creating any file at workspace root.**

## 🚫 Root is LOCKED

**NEVER create files at root level.** This workspace was cleaned on 2026-03-19 from 376 files → 40.

### Files that MUST stay at root

| Category | Files |
|----------|-------|
| AI Config | `AGENTS.md`, `CLAUDE.md`, `SKILL_CATALOG.md`, `docs/guides/IDE_OPERATING_MANUAL.md` |
| CLI | `ag.py`, `ag.cmd`, `ag-*.cmd`, `yolo.py`, `yolo.cmd`, `idea_nam.cmd` |
| Launchers | `CEO_AUTOPILOT.cmd`, `START_CEO_AUTOPILOT.cmd` |
| Dashboard | `dashboard.py`, `aom_logger.py`, `obsidian_helper.py` |
| Package | `package.json`, `requirements_master.txt`, `LICENSE`, `README.md` |
| Config | `.env`, `.gitignore`, `.editorconfig`, `.mcp.json` |

### Everything else goes in a subfolder

| File Type | Target Folder |
|-----------|---------------|
| Python script | `scripts/` |
| Report/Summary | `reports/` |
| Handoff | `handoffs/` |
| Documentation | `docs/` |
| Test file | `tests/` |
| Config/Data | `config/` or `data/` |
| Screenshot | `screenshots/` |
| Plan | `plans/` |
| Log | `logs/` |
| Batch/.cmd | `scripts/` or project-specific `bin/` |

## 🏠 Project Structure

| # | Project | Priority | Status |
|---|---------|----------|--------|
| 8 | `8.P8_SEO_Clean/` | 🔴 Core | ✅ Clean |
| 6 | `6.Osidian_database/` | 🔴 Core | ✅ Clean |
| 3 | `3.Smart_Knowledge_Architect/` | ⚠️ Active | Has rules |
| 4 | `4.ESTC_Proposal/` | ⚠️ Active | Has rules |
| 5 | `5.predictive_maintenance/` | ℹ️ Side | Clean |
| 2 | `2.SEO_web_app/` | ⛔ DEPRECATED | Do not use |

---
*Updated: 2026-03-19 — Post-cleanup enforcement*
