# 御魂匠（YYS Helper）

一个针对 Windows + MuMu 模拟器的本地《阴阳师》助手。它以 ADB 截图、RapidOCR/MNN 和受保护的状态机为核心，不读取游戏进程内存、不注入客户端，也不会自动充值或消耗勾玉。

## 当前能力

- 导入并校验 `|TA|...` 文字方案码，接受 PNG/JPG/WEBP 二维码图片。
- 从六个位置、套装数量、主属性和总属性约束中求解当前库存的最优六件套；严格解不存在时返回最小缺口方案。
- 输出、控制、辅助、速度四类评分模板。
- 识别并保护已装备、已锁定、低置信度、方案引用、六星速度胚及三有效词条御魂。
- 按方案缺口和预计金币效率推荐胚子，自动强化时每 `+3` 重新扫描并止损。
- 困 28 与御魂副本的受控状态机：每次点击前识别当前场景，点击后验证状态变化。
- 次数/时长上限、体力不足、掉线、背包满、连续三次识别失败自动停止；`F12` 紧急停止。
- 本地 SQLite 仓库和操作审计；无任何云端上传。
- 演示模式可在未安装 MuMu 时体验库存、配装和强化建议。

> 首版的困 28 不自动更换满级狗粮。游戏界面更新可能改变 OCR 文案或按钮位置；未知场景下助手会停止，不会猜测坐标继续点击。

## 安装

需要 Windows 10/11、Python 3.11 或 3.12，以及已经安装并启动的 MuMu 模拟器。

在 PowerShell 中进入项目目录：

```powershell
.\scripts\setup.ps1
```

如果 `python` 不是你的 Python 3.11/3.12 路径：

```powershell
.\scripts\setup.ps1 -Python "C:\Path\To\python.exe"
```

## 启动

先体验演示数据：

```powershell
.\scripts\start.ps1 -Demo
```

连接真实 MuMu：

```powershell
.\scripts\start.ps1
```

点击右上角“连接 MuMu”。助手会优先查找 MuMu 自带的 `adb.exe`；没有找到时会让你手动选择。请确保 MuMu 已启动，且调试/ADB 功能已开启。

## 推荐操作顺序

1. 在“总览”连接 MuMu，确认能看到实时截图。
2. 在“方案配装”粘贴文字方案码或选择二维码图片。
3. 查看“御魂仓库”的评分与保护状态。
4. 在“强化建议”设置金币和胚子数量预算，按 `+3` 检查点逐步强化。
5. 在“日常任务”设置最大循环和最长运行时间，再启动困 28 或御魂副本。
6. 任何时候按 `F12`，助手都会停止产生新的游戏输入。

## 安全边界

- 自动弃置前会强制执行保护规则；OCR 置信度低于 `0.92` 的御魂不执行破坏性动作。
- 不提供购买体力、充值、勾玉消费或绕过游戏检测的功能。
- 方案码作为数据参数处理，不拼接到 shell 命令。
- 日志、截图和数据库默认写入本机 `data/` / `logs/`，这些目录不会提交到 Git。
- 强化词条具有随机性，助手只估计潜力并分段止损，不承诺最终属性。

使用自动化工具可能受到游戏服务条款限制。请先用小循环和低预算验证识别效果，并自行承担账号风险。

## 开发与测试

领域测试不依赖 GUI 或真实模拟器：

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

设计与执行计划位于：

- `docs/superpowers/specs/2026-09-18-yys-helper-design.md`
- `docs/superpowers/plans/2026-09-18-yys-helper-mvp.md`

## 项目结构

```text
src/yys_helper/
  application/     方案、御魂和真实 MuMu 运行时
  automation/      可取消状态机与任务流程
  domain/          模型、评分、保护、配装和强化算法
  infrastructure/  ADB、OCR 和 SQLite
  ui/              PySide6 桌面界面
tests/              纯本地自动化测试
scripts/            Windows 安装和启动脚本
```
