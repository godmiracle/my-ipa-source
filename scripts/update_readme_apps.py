#!/usr/bin/env python3
"""Update the generated supported-app table in README.md."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "all-apps.json"
README_PATH = ROOT / "README.md"
BEGIN_MARKER = "<!-- BEGIN GENERATED APP LIST -->"
END_MARKER = "<!-- END GENERATED APP LIST -->"


def compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def markdown_cell(value: Any) -> str:
    return compact_text(value).replace("|", "\\|")


def render_app_list(source: dict[str, Any]) -> str:
    apps = source.get("apps")
    if not isinstance(apps, list):
        raise ValueError("all-apps.json field 'apps' must be an array")

    lines = [
        f"当前源收录 **{len(apps)}** 个应用；版本信息来自 AltGallery 与已配置的 GitHub Releases 仓库。",
        "",
        "| 应用 | 简介 | 当前版本 | 最低系统 |",
        "| --- | --- | --- | --- |",
    ]
    for app in apps:
        if not isinstance(app, dict):
            raise ValueError("Every app in all-apps.json must be an object")
        versions = app.get("versions")
        if not isinstance(versions, list) or not versions:
            raise ValueError(f"App has no versions: {app.get('name', '<unnamed>')}")
        latest = versions[0]
        if not isinstance(latest, dict):
            raise ValueError(f"Latest version is not an object: {app.get('name', '<unnamed>')}")
        name = markdown_cell(app.get("name"))
        subtitle = markdown_cell(app.get("subtitle") or app.get("localizedDescription"))
        version = markdown_cell(latest.get("version") or "未声明")
        min_os = markdown_cell(latest.get("minOSVersion") or "未声明")
        lines.append(f"| {name} | {subtitle} | `{version}` | iOS {min_os} |")
    return "\n".join(lines)


def replace_app_list(readme: str, app_list: str) -> str:
    pattern = re.compile(
        rf"{re.escape(BEGIN_MARKER)}.*?{re.escape(END_MARKER)}",
        re.DOTALL,
    )
    replacement = f"{BEGIN_MARKER}\n{app_list}\n{END_MARKER}"
    updated, count = pattern.subn(replacement, readme, count=1)
    if count != 1:
        raise ValueError("README.md is missing the generated app-list markers")
    return updated


def main() -> int:
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    readme = README_PATH.read_text(encoding="utf-8")
    updated = replace_app_list(readme, render_app_list(source))
    if updated != readme:
        README_PATH.write_text(updated, encoding="utf-8")
    print(f"Updated supported-app list in {README_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
