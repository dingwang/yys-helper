# Real Inventory Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace demo-only inventory in normal mode with read-only OCR capture from MuMu and use captured souls for build and upgrade recommendations.

**Architecture:** Pure parsers convert OCR boxes into domain models. SQLite remains the source of truth, while the Qt window rebuilds its derived state after every successful capture. The game remains responsible for resolving opaque scheme codes; the helper reads only visible scheme constraints.

**Tech Stack:** Python 3.11, PySide6, RapidOCR/MNN, SQLite, `unittest`

**Spec:** `docs/superpowers/specs/2026-09-18-real-inventory-design.md`

## Global Constraints

- Real capture is read-only and sends no ADB input.
- OCR confidence below `0.92` is protected and marked for review.
- Normal mode never falls back to demo inventory.
- Destructive soul actions remain disabled in this delivery.

---

### Task 1: Parse soul detail screenshots

**Files:**
- Create: `src/yys_helper/application/inventory_capture.py`
- Create: `tests/test_inventory_capture.py`

**Interfaces:**
- Produces: `SoulDetailParser.parse(boxes, *, slot, rarity, set_name_override="") -> Soul`
- Produces: `SoulParseError`

- [x] Write tests for a complete six-star soul, percentage attributes, lock/equip flags and missing required fields.
- [x] Run `python -m unittest tests.test_inventory_capture.SoulDetailParserTests -v` and verify RED.
- [x] Implement line normalization, stat parsing, confidence aggregation and stable fingerprint IDs.
- [x] Re-run the focused tests and verify GREEN.

### Task 2: Parse visible scheme constraints and derive real state

**Files:**
- Modify: `src/yys_helper/application/inventory_capture.py`
- Modify: `src/yys_helper/demo.py`
- Modify: `tests/test_inventory_capture.py`
- Modify: `tests/test_demo.py`

**Interfaces:**
- Produces: `SchemeRequirementParser.parse(boxes, *, weights) -> BuildRequirement`
- Produces: `create_state(inventory, requirement) -> DemoState`

- [x] Write tests for set counts, slot main stats, minimum speed, full critical rate and an empty real inventory.
- [x] Run focused tests and verify RED.
- [x] Implement the requirement parser and shared derived-state builder.
- [x] Re-run focused tests and verify GREEN.

### Task 3: Wire real capture into the desktop UI

**Files:**
- Modify: `src/yys_helper/ui/app.py`
- Modify: `src/yys_helper/ui/main_window.py`
- Modify: `tests/test_ui_smoke.py`

**Interfaces:**
- Normal startup consumes `AppRepository.list_souls()`.
- Inventory page emits `capture_requested(set_name, slot, rarity)`.
- Scheme page emits `read_game_requested()`.

- [x] Write GUI tests proving normal mode starts empty and a captured soul refreshes the table.
- [x] Run focused UI tests and verify RED.
- [x] Add capture controls, read-only OCR handlers and refreshable pages.
- [x] Re-run focused UI tests and verify GREEN.

### Task 4: Documentation, verification and delivery

**Files:**
- Modify: `README.md`

- [x] Document the real capture workflow, the opaque scheme-code boundary and read-only safety model.
- [x] Run `python -m unittest discover -s tests -v`.
- [x] Run `python -m compileall -q src tests` and `python -m pip check`.
- [x] Run `git diff --check`, commit, push `main`, and verify local/remote hashes match.
