# 阴阳师助手 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个可运行、可测试的 Windows 图形助手，通过 MuMu ADB 完成御魂方案配装、缺口强化规划及困 28/御魂副本自动循环。

**Architecture:** 纯 Python 领域层负责评分、组合优化和安全规则；基础设施层封装 ADB、OCR 与 SQLite；可取消状态机在执行每个输入动作前后验证场景。PySide6 页面只消费应用服务，耗时任务放入后台线程。

**Tech Stack:** Python 3.11+、PySide6、OpenCV、RapidOCR、ONNX Runtime、SQLite、`unittest`

**Spec:** `docs/superpowers/specs/2026-09-18-yys-helper-design.md`

## Global Constraints

- 仅支持 Windows MuMu；基准分辨率 `1280x720`，点击坐标归一化。
- 禁止进程注入、内存读取、反作弊规避、充值及勾玉消费。
- 破坏性动作要求 OCR 置信度不低于 `0.92` 且通过保护策略。
- 强化以 `+3` 为检查点并受金币、材料、数量与等级预算限制。
- 连续三次识别失败、ADB 断开、体力不足或用户 `F12` 必须停止。
- 数据仅存本地 SQLite；仓库不得包含账号数据或游戏截图。

---

### Task 1: 项目骨架与领域模型

**Files:**
- Create: `pyproject.toml`
- Create: `src/yys_helper/domain/models.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Produces: `Soul`, `Stat`, `BuildRequirement`, `BuildResult`, `UpgradeBudget`, `StopReason`。

- [ ] **Step 1: Write the failing tests**

```python
def test_soul_rejects_slot_outside_one_to_six(self):
    with self.assertRaises(ValueError):
        Soul(id="x", set_name="招财猫", slot=7, rarity=6, level=0,
             main_stat=Stat.SPEED, main_value=57, substats={})
```

- [ ] **Step 2: Verify RED**

Run: `python -m unittest tests.test_models -v`
Expected: FAIL because the model module does not exist.

- [ ] **Step 3: Implement frozen validated dataclasses and enums**

`Stat` is a string enum; slots accept `1..6`, rarity `1..6`, level `0..15`, confidence `0..1`, and budget fields reject negative values.

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m unittest tests.test_models -v`
Expected: PASS.

Commit: `feat: add project foundation and soul models`

### Task 2: 评分、保护、配装与强化规划

**Files:**
- Create: `src/yys_helper/domain/scoring.py`
- Create: `src/yys_helper/domain/safety.py`
- Create: `src/yys_helper/domain/optimizer.py`
- Create: `src/yys_helper/domain/upgrade.py`
- Create: `tests/test_scoring.py`
- Create: `tests/test_optimizer.py`
- Create: `tests/test_upgrade.py`

**Interfaces:**
- Consumes: Task 1 models.
- Produces: `score_soul`, `protection_reasons`, `optimize_build`, `rank_upgrade_candidates`。

- [ ] **Step 1: Write scoring/protection tests and verify RED**

```python
def test_equipped_soul_is_always_protected(self):
    item = replace(make_soul("used", 2), equipped_to="鬼使黑")
    self.assertIn("equipped", protection_reasons(item, set()))
```

Run: `python -m unittest tests.test_scoring -v`
Expected: FAIL because scoring and safety modules are missing.

- [ ] **Step 2: Implement profile scoring and immutable protection reasons; verify GREEN**

Run: `python -m unittest tests.test_scoring -v`
Expected: PASS for speed priority, useful-stat counts, equipped, locked, referenced and low-confidence cases.

- [ ] **Step 3: Write optimizer tests and verify RED**

```python
def test_optimizer_returns_closest_build_when_strict_solution_missing(self):
    result = optimize_build(inventory_fixture(), speed_requirement(min_speed=300))
    self.assertFalse(result.satisfied)
    self.assertEqual(6, len(result.souls))
    self.assertGreater(result.shortfalls[Stat.SPEED], 0)
```

Run: `python -m unittest tests.test_optimizer -v`
Expected: FAIL because optimizer is missing.

- [ ] **Step 4: Implement bounded search and verify GREEN**

Keep top 20 eligible candidates per slot, enumerate six slots, enforce set counts/main stats, prune by optimistic score, and rank near-solutions by normalized shortfall.

Run: `python -m unittest tests.test_optimizer -v`
Expected: PASS.

- [ ] **Step 5: Write upgrade tests, implement `+3` ranking, verify GREEN and commit**

```python
def test_upgrade_planner_prefers_relevant_low_level_embryo(self):
    items = rank_upgrade_candidates(fixture(), requirement(), budget())
    self.assertEqual("speed-embryo", items[0].soul.id)
    self.assertEqual(3, items[0].next_level)
```

Run before and after: `python -m unittest tests.test_upgrade -v`
Expected: first FAIL, then PASS.

Commit: `feat: add soul scoring optimization and upgrade planning`

### Task 3: MuMu ADB、视觉接口与本地仓储

**Files:**
- Create: `src/yys_helper/infrastructure/adb.py`
- Create: `src/yys_helper/infrastructure/vision.py`
- Create: `src/yys_helper/infrastructure/repository.py`
- Create: `tests/test_adb.py`
- Create: `tests/test_vision.py`
- Create: `tests/test_repository.py`

**Interfaces:**
- Produces: `AdbClient`, `VisionService`, `AppRepository`。

- [ ] **Step 1: Write ADB contract tests and verify RED**

```python
def test_screenshot_targets_selected_serial(self):
    runner = RecordingRunner(stdout=b"\x89PNG\r\n\x1a\n")
    client = AdbClient("adb.exe", "127.0.0.1:16384", runner=runner)
    self.assertTrue(client.screenshot().startswith(b"\x89PNG"))
    self.assertEqual("127.0.0.1:16384", runner.calls[0][2])
```

Run: `python -m unittest tests.test_adb -v`
Expected: FAIL because ADB wrapper is missing.

- [ ] **Step 2: Implement discovery/devices/screenshot/tap/swipe/text with timeouts; verify GREEN**

Run: `python -m unittest tests.test_adb -v`
Expected: PASS, including timeout and malformed PNG cases.

- [ ] **Step 3: Write vision tests, implement lazy OCR adapter, verify GREEN**

```python
def test_find_text_rejects_low_confidence(self):
    vision = VisionService(engine=FakeOcr([ocr_box("挑战", 0.80)]))
    self.assertIsNone(vision.find_text(image(), "挑战", 0.92))
```

Run before and after: `python -m unittest tests.test_vision -v`
Expected: first FAIL, then PASS without importing native packages in tests.

- [ ] **Step 4: Write SQLite round-trip test, implement schema, verify GREEN and commit**

Run before and after: `python -m unittest tests.test_repository -v`
Expected: first FAIL, then PASS for souls, settings and audit events.

Commit: `feat: integrate MuMu ADB vision and local storage`

### Task 4: 可取消状态机与日常任务

**Files:**
- Create: `src/yys_helper/automation/engine.py`
- Create: `src/yys_helper/automation/workflows.py`
- Create: `tests/test_engine.py`
- Create: `tests/test_workflows.py`

**Interfaces:**
- Produces: `AutomationEngine.run`, `chapter_28_workflow`, `soul_dungeon_workflow`。

- [ ] **Step 1: Write state/guard tests and verify RED**

```python
def test_three_unknown_scenes_stop_without_input(self):
    engine = AutomationEngine(FakeObserver([None, None, None]), RecordingActor())
    result = engine.run(workflow_fixture(), limits())
    self.assertEqual(StopReason.UNRECOGNIZED_SCENE, result.reason)
    self.assertEqual([], engine.actor.actions)
```

Run: `python -m unittest tests.test_engine -v`
Expected: FAIL because engine is missing.

- [ ] **Step 2: Implement cancellation, limits and verified transitions; verify GREEN**

Run: `python -m unittest tests.test_engine -v`
Expected: PASS for cancellation, unknown scenes, stamina, max rounds and max duration.

- [ ] **Step 3: Write workflow graph tests, implement both graphs, verify GREEN and commit**

```python
def test_chapter_28_returns_to_map_after_settlement(self):
    self.assertEqual("explore_map", chapter_28_workflow().next_state("settlement", "confirm"))
```

Run before and after: `python -m unittest tests.test_workflows -v`
Expected: first FAIL, then PASS.

Commit: `feat: add guarded daily automation workflows`

### Task 5: 方案码与阶段强化服务

**Files:**
- Create: `src/yys_helper/application/schemes.py`
- Create: `src/yys_helper/application/souls.py`
- Create: `tests/test_schemes.py`
- Create: `tests/test_soul_service.py`

**Interfaces:**
- Produces: `normalize_scheme_code`, `SchemeService`, `SoulService.upgrade_and_replan`。

- [ ] **Step 1: Write scheme validation tests and verify RED**

```python
def test_normalizes_ta_code(self):
    self.assertEqual("|TA|abc123", normalize_scheme_code("  |TA|abc123\n"))

def test_rejects_shell_metacharacters(self):
    with self.assertRaises(InvalidSchemeCode):
        normalize_scheme_code("|TA|abc;rm")
```

Run: `python -m unittest tests.test_schemes -v`
Expected: FAIL because scheme service is missing.

- [ ] **Step 2: Implement safe text/QR import contract and verify GREEN**

Run: `python -m unittest tests.test_schemes -v`
Expected: PASS; codes are always passed as subprocess data arguments.

- [ ] **Step 3: Write staged-upgrade orchestration test and verify RED**

```python
def test_rescans_at_plus_three_and_stops_after_bad_roll(self):
    outcome = scripted_service([level0(), bad_level3()]).upgrade_and_replan(requirement(), budget())
    self.assertEqual([3], outcome.requested_levels)
    self.assertEqual("potential_lost", outcome.stop_reason)
```

Run: `python -m unittest tests.test_soul_service -v`
Expected: FAIL because orchestration is missing.

- [ ] **Step 4: Implement scan/plan/mark/upgrade/replan; verify GREEN and commit**

Run: `python -m unittest tests.test_soul_service -v`
Expected: PASS, including protected-item and exhausted-budget cases.

Commit: `feat: orchestrate scheme builds and staged soul upgrades`

### Task 6: 图形界面、演示模式和交付

**Files:**
- Create: `src/yys_helper/ui/app.py`
- Create: `src/yys_helper/ui/main_window.py`
- Create: `src/yys_helper/demo.py`
- Create: `src/yys_helper/__main__.py`
- Create: `tests/test_demo.py`
- Create: `README.md`
- Create: `scripts/setup.ps1`
- Create: `scripts/start.ps1`

**Interfaces:**
- Consumes: Tasks 2-5.
- Produces: `python -m yys_helper` and `python -m yys_helper --demo`。

- [ ] **Step 1: Write demo journey test and verify RED**

```python
def test_demo_contains_inventory_build_and_upgrade_candidate(self):
    demo = create_demo_state()
    self.assertGreater(len(demo.inventory), 6)
    self.assertEqual(6, len(demo.closest_build.souls))
    self.assertGreater(len(demo.upgrade_candidates), 0)
```

Run: `python -m unittest tests.test_demo -v`
Expected: FAIL because demo module is missing.

- [ ] **Step 2: Implement deterministic demo data and verify GREEN**

Run: `python -m unittest tests.test_demo -v`
Expected: PASS.

- [ ] **Step 3: Implement UI and startup scripts**

Use a dark indigo/gold theme, 220px navigation rail, five pages, persistent logs, red emergency-stop button and F12 shortcut. Import PySide6 only in `ui/`.

- [ ] **Step 4: Document setup, MuMu connection, scheme workflow, budgets, protection and risk**

`setup.ps1` creates `.venv` and installs `.[desktop]`; `start.ps1` validates the environment and forwards `--demo`.

- [ ] **Step 5: Run final verification and commit**

Run: `python -m unittest discover -s tests -v`
Expected: zero failures/errors.

Run: `python -m compileall -q src tests`
Expected: exit code 0.

Run: `git diff --check`
Expected: no output.

Commit: `feat: deliver yys helper desktop MVP`
