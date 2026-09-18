# Reliable Inventory and Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make real soul acquisition diagnosable and useful by fixing title-dependent OCR parsing, adding local evidence bundles, importing supported JSON snapshots, and preserving unknown automation scenes.

**Architecture:** Pure parsers remain independent of Qt and ADB. A diagnostics writer serializes screenshots and OCR boxes under ignored local data, while the UI coordinates capture/import and refreshes derived state. Repository writes are transactional; automation never clicks an unknown scene.

**Tech Stack:** Python 3.11, PySide6, Pillow, RapidOCR/MNN, SQLite, `unittest`

**Spec:** `docs/superpowers/specs/2026-09-18-repetition-reduction-design.md`

## Global Constraints

- Do not read process memory, inject code, intercept network traffic, or add anti-cheat evasion.
- Capture and import are read-only with respect to the game.
- Diagnostics stay under ignored `data/diagnostics/` and never enter Git.
- Missing required soul fields must not write partial records.
- Unknown automation scenes must cause zero input and save the last observable evidence.
- Existing SQLite data must remain readable without a destructive migration.

---

### Task 1: Local capture evidence bundles

**Files:**
- Create: `src/yys_helper/infrastructure/diagnostics.py`
- Create: `tests/test_diagnostics.py`
- Modify: `src/yys_helper/application/runtime.py`
- Modify: `tests/test_runtime.py`

**Interfaces:**
- Produces: `CaptureEvidenceWriter(root: Path).write(purpose: str, png: bytes, boxes: Iterable[OcrBox], metadata: Mapping[str, object], error: str | None = None) -> Path`
- Produces: `OcrMumuRuntime.capture_evidence() -> tuple[bytes, tuple[OcrBox, ...]]`

- [x] **Step 1: Write failing evidence serialization tests**

```python
def test_writer_saves_png_and_machine_readable_ocr(self):
    folder = CaptureEvidenceWriter(root).write(
        "soul-detail", PNG, [OcrBox("招财猫", 0.88, (1, 2, 3, 4))],
        {"serial": "emulator-5556"}, error="missing level"
    )
    self.assertEqual(PNG, (folder / "screen.png").read_bytes())
    payload = json.loads((folder / "ocr.json").read_text("utf-8"))
    self.assertEqual("招财猫", payload["boxes"][0]["text"])
    self.assertEqual("missing level", payload["error"])
```

- [x] **Step 2: Run `python -m unittest tests.test_diagnostics -v` and verify failure because the module is absent**

- [x] **Step 3: Implement sanitized purpose names, UTC timestamp directories, atomic JSON creation, and runtime raw capture**

```python
def capture_evidence(self) -> tuple[bytes, tuple[OcrBox, ...]]:
    with self._io_lock:
        png = self.adb.screenshot()
        image = Image.open(BytesIO(png)).convert("RGB")
        return png, tuple(self.vision.read(image))
```

- [x] **Step 4: Re-run focused tests and commit**

Run: `python -m unittest tests.test_diagnostics tests.test_runtime -v`

Commit: `feat: save local OCR evidence bundles`

### Task 2: Parse current detail panels without a fixed title

**Files:**
- Modify: `src/yys_helper/application/inventory_capture.py`
- Modify: `tests/test_inventory_capture.py`

**Interfaces:**
- Preserves: `SoulDetailParser.parse(boxes, *, slot, rarity, set_name_override="") -> Soul`
- Produces: `SoulParseError.stage: str` with values `page`, `set`, `level`, or `stats`

- [x] **Step 1: Add a failing title-free detail test**

```python
def test_parses_detail_panel_without_synthetic_title_anchor(self):
    boxes = (
        OcrBox("招财猫", .97, (900, 80, 1120, 112)),
        OcrBox("+15", .91, (900, 125, 990, 158)),
        OcrBox("速度 57", .89, (900, 210, 1120, 244)),
        OcrBox("暴击 +6%", .87, (900, 270, 1120, 304)),
    )
    soul = SoulDetailParser().parse(boxes, slot=2, rarity=6)
    self.assertEqual(("招财猫", 15, Stat.SPEED),
                     (soul.set_name, soul.level, soul.main_stat))
```

- [x] **Step 2: Run the test and verify `当前画面不像御魂详情页`**

- [x] **Step 3: Replace the mandatory title anchor with spatial evidence**

Accept a panel when a known/overridden set name and a valid level exist within one horizontal cluster and at least one parsable stat occurs below the level. Use `0.65` only for structural candidates, preserve the minimum actual confidence on the resulting soul, and keep missing critical fields as hard errors.

- [x] **Step 4: Add negative tests for unrelated stat fragments and verify the parser suite**

Run: `python -m unittest tests.test_inventory_capture.SoulDetailParserTests -v`

Commit: `fix: recognize title-free soul detail panels`

### Task 3: Import full inventory JSON safely

**Files:**
- Create: `src/yys_helper/application/inventory_import.py`
- Create: `tests/test_inventory_import.py`
- Modify: `src/yys_helper/infrastructure/repository.py`
- Modify: `tests/test_repository.py`

**Interfaces:**
- Produces: `InventoryImportError(ValueError)`
- Produces: `ImportPreview(format_name: str, souls: tuple[Soul, ...], warnings: tuple[str, ...])`
- Produces: `parse_inventory_json(payload: bytes) -> ImportPreview`
- Produces: `AppRepository.replace_souls(souls: Iterable[Soul]) -> None`

- [x] **Step 1: Write failing native and Fluxxu-format parser tests**

```python
def test_imports_fluxxu_snapshot(self):
    payload = {"data": {"hero_equips": [{
        "id": "abc", "suit_id": 300010, "pos": 1, "quality": 6,
        "level": 15, "lock": True, "garbage": False,
        "base_attr": {"type": "Speed", "value": 57.0},
        "attrs": [{"type": "CritRate", "value": .06}],
        "single_attrs": []
    }]}}
    preview = parse_inventory_json(json.dumps(payload).encode())
    self.assertEqual("fluxxu", preview.format_name)
    self.assertEqual(("招财猫", 2, 57.0),
                     (preview.souls[0].set_name, preview.souls[0].slot,
                      preview.souls[0].main_value))
```

- [x] **Step 2: Run focused tests and verify failure because the importer is absent**

- [x] **Step 3: Implement strict format detection and field mapping**

Support `yys-helper.inventory.v1`, Fluxxu `data.hero_equips`, and new-client `equip_data`. Map `Hp/Defense/Attack/HpRate/DefenseRate/AttackRate/Speed/CritRate/CritPower/EffectHitRate/EffectResistRate` to `Stat`; multiply rate values by 100; reject unknown suit IDs and malformed records with indexed messages. Use stable source IDs prefixed by format.

- [x] **Step 4: Implement transactional replacement and rollback test**

```python
def replace_souls(self, souls):
    with self.connection:
        self.connection.execute("DELETE FROM souls")
        for soul in souls:
            self.connection.execute(INSERT_SOUL_SQL, (soul.id, self._soul_payload(soul)))
```

- [x] **Step 5: Run importer and repository tests and commit**

Run: `python -m unittest tests.test_inventory_import tests.test_repository -v`

Commit: `feat: import complete soul inventory snapshots`

### Task 4: Expose capture diagnostics and JSON import in the GUI

**Files:**
- Modify: `src/yys_helper/ui/main_window.py`
- Modify: `tests/test_ui_smoke.py`

**Interfaces:**
- Inventory page emits `import_requested(Path)`.
- `MainWindow.import_inventory(path: Path) -> None` parses, confirms, transactionally replaces, and refreshes state.
- `MainWindow.capture_current_soul(...)` writes an evidence bundle on success or failure.

- [x] **Step 1: Write failing UI tests for import refresh and failed-capture evidence**

```python
def test_inventory_import_replaces_local_inventory_after_confirmation(self):
    with patch.object(window, "_confirm_inventory_import", return_value=True):
        window.import_inventory(snapshot_path)
    self.assertEqual(1, window.inventory_page.table.rowCount())
    self.assertIn("导入 1 枚", window.log.toPlainText())
```

- [x] **Step 2: Run focused UI tests and verify missing controls/handlers**

- [x] **Step 3: Add `导入库存 JSON` and `保存诊断采集` controls**

The import dialog accepts only `.json`. Preview shows format, total, locked, discarded, low-confidence and warning counts. Confirmation text states that the local snapshot will be replaced and the game will not be modified.

- [x] **Step 4: Route raw capture through `capture_evidence`, persist bundle, parse the same boxes, and include the folder in errors**

- [x] **Step 5: Verify UI tests and commit**

Run: `python -m unittest tests.test_ui_smoke -v`

Commit: `feat: add inventory import and capture diagnostics UI`

### Task 5: Preserve unknown automation scenes

**Files:**
- Modify: `src/yys_helper/automation/engine.py`
- Modify: `src/yys_helper/application/runtime.py`
- Modify: `src/yys_helper/ui/main_window.py`
- Modify: `tests/test_engine.py`
- Modify: `tests/test_ui_smoke.py`

**Interfaces:**
- Produces: `OcrMumuRuntime.last_capture_png: bytes | None`
- `AutomationWorker` emits the final runtime evidence when stop reason is `UNRECOGNIZED_SCENE`.

- [x] **Step 1: Write a failing test proving three unknown scenes perform no input and expose the final capture**

- [x] **Step 2: Keep the latest PNG and OCR boxes in runtime without altering actor state**

- [x] **Step 3: On unknown-scene completion, save `automation-unknown` evidence and log its path**

- [x] **Step 4: Run engine/runtime/UI suites and commit**

Run: `python -m unittest tests.test_engine tests.test_runtime tests.test_ui_smoke -v`

Commit: `feat: preserve unknown automation scene evidence`

### Task 6: Documentation and release verification

**Files:**
- Modify: `README.md`
- Modify: `pyproject.toml`

**Interfaces:**
- Bumps package version from `0.2.0` to `0.3.0`.

- [x] **Step 1: Document the two inventory paths, diagnostic location, supported JSON formats, and safe next-run workflow**

- [x] **Step 2: Run full verification**

Run: `python -m unittest discover -s tests -v`

Run: `python -m compileall -q src tests`

Run: `python -m pip check`

Run: `git diff --check`

- [x] **Step 3: Commit release metadata and push `main` after the user-requested direct-delivery policy**

Commit: `release: deliver diagnosable real inventory workflow`
