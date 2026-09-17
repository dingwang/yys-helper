from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(description="阴阳师 MuMu 助手")
    parser.add_argument("--demo", action="store_true", help="使用演示库存启动")
    args = parser.parse_args()
    try:
        from yys_helper.ui.app import run_app
    except ImportError as exc:
        if exc.name and exc.name.startswith("PySide6"):
            parser.error("缺少桌面依赖，请先运行 scripts/setup.ps1")
        raise
    return run_app(demo_mode=args.demo)


if __name__ == "__main__":
    raise SystemExit(main())
