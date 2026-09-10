#!/usr/bin/env python3
"""Build a personal AltStore source for LiveContainer.

The generated all-apps.json is composed from a cached upstream source and
user-maintained extra app/news entries. The script intentionally uses only the
Python standard library so it can run in GitHub Actions without dependencies.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "source.json"


class SourceError(ValueError):
    """Raised when an AltStore source is malformed."""


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise SourceError(f"Missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SourceError(f"Invalid JSON in {path}: {exc}") from exc


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temporary.replace(path)


def resolve_config_path(config_value: str) -> Path:
    path = ROOT / config_value
    return path.resolve()


def fetch_json(url: str) -> Any:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "personal-livecontainer-source/1.0",
        },
    )
    try:
        with urlopen(request, timeout=60) as response:
            payload = response.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise SourceError(f"Unable to fetch upstream source {url}: {exc}") from exc

    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceError(f"Upstream response is not valid UTF-8 JSON: {url}") from exc


def app_identity(app: dict[str, Any]) -> str:
    return str(app.get("bundleIdentifier", ""))


def selected_upstream_apps(
    upstream: dict[str, Any],
    upstream_config: dict[str, Any],
) -> list[dict[str, Any]]:
    apps = upstream.get("apps", [])
    if not isinstance(apps, list):
        raise SourceError("Upstream source field 'apps' must be an array")

    include_names = upstream_config.get("includeAppNames")
    include_bundles = upstream_config.get("includeBundleIdentifiers")
    exclude_names = set(upstream_config.get("excludeAppNames") or [])
    exclude_bundles = set(upstream_config.get("excludeBundleIdentifiers") or [])

    if include_names is not None and not isinstance(include_names, list):
        raise SourceError("upstream.includeAppNames must be an array or null")
    if include_bundles is not None and not isinstance(include_bundles, list):
        raise SourceError(
            "upstream.includeBundleIdentifiers must be an array or null"
        )

    included_names = set(include_names or [])
    included_bundles = set(include_bundles or [])
    has_allowlist = include_names is not None or include_bundles is not None

    selected: list[dict[str, Any]] = []
    for app in apps:
        if not isinstance(app, dict):
            raise SourceError("Every upstream app must be an object")
        name = app.get("name")
        bundle = app_identity(app)

        if name in exclude_names or bundle in exclude_bundles:
            continue
        if has_allowlist and name not in included_names and bundle not in included_bundles:
            continue
        selected.append(app)
    return selected


def merge_by_bundle(
    upstream_apps: list[dict[str, Any]], extra_apps: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    result = list(upstream_apps)
    indexes: dict[str, int] = {}
    for index, app in enumerate(result):
        bundle = app_identity(app)
        if bundle:
            indexes[bundle] = index

    for app in extra_apps:
        if not isinstance(app, dict):
            raise SourceError("Every extra app must be an object")
        bundle = app_identity(app)
        if not bundle:
            raise SourceError("Every extra app must have bundleIdentifier")
        if bundle in indexes:
            result[indexes[bundle]] = app
        else:
            indexes[bundle] = len(result)
            result.append(app)
    return result


def merge_news(
    upstream_news: list[dict[str, Any]],
    extra_news: list[dict[str, Any]],
    included_bundles: set[str],
) -> list[dict[str, Any]]:
    result = [
        item
        for item in upstream_news
        if isinstance(item, dict)
        and (not item.get("appID") or item.get("appID") in included_bundles)
    ]
    indexes: dict[str, int] = {}
    for index, item in enumerate(result):
        identifier = item.get("identifier")
        if identifier:
            indexes[str(identifier)] = index

    for item in extra_news:
        if not isinstance(item, dict):
            raise SourceError("Every extra news entry must be an object")
        app_id = item.get("appID")
        if app_id and app_id not in included_bundles:
            raise SourceError(
                f"Extra news entry refers to an app not present in the source: {app_id}"
            )
        identifier = item.get("identifier")
        if identifier and str(identifier) in indexes:
            result[indexes[str(identifier)]] = item
        else:
            if identifier:
                indexes[str(identifier)] = len(result)
            result.append(item)
    return result


def validate_source(source: dict[str, Any]) -> None:
    if not isinstance(source, dict):
        raise SourceError("Source root must be an object")
    if not isinstance(source.get("name"), str) or not source["name"].strip():
        raise SourceError("Source must have a non-empty name")
    apps = source.get("apps")
    if not isinstance(apps, list):
        raise SourceError("Source field 'apps' must be an array")

    seen_bundles: set[str] = set()
    for index, app in enumerate(apps):
        if not isinstance(app, dict):
            raise SourceError(f"apps[{index}] must be an object")
        for key in ("name", "bundleIdentifier", "versions"):
            if key not in app:
                raise SourceError(f"apps[{index}] is missing {key}")
        bundle = app["bundleIdentifier"]
        if not isinstance(bundle, str) or not bundle.strip():
            raise SourceError(f"apps[{index}].bundleIdentifier must be a non-empty string")
        if bundle in seen_bundles:
            raise SourceError(f"Duplicate bundleIdentifier: {bundle}")
        seen_bundles.add(bundle)

        versions = app["versions"]
        if not isinstance(versions, list) or not versions:
            raise SourceError(f"apps[{index}].versions must be a non-empty array")
        for version_index, version in enumerate(versions):
            if not isinstance(version, dict):
                raise SourceError(
                    f"apps[{index}].versions[{version_index}] must be an object"
                )
            if not isinstance(version.get("version"), str) or not version["version"].strip():
                raise SourceError(
                    f"apps[{index}].versions[{version_index}] needs a non-empty version"
                )
            download_url = version.get("downloadURL")
            if not isinstance(download_url, str) or not download_url.startswith("https://"):
                raise SourceError(
                    f"apps[{index}].versions[{version_index}].downloadURL must be an HTTPS URL"
                )

    news = source.get("news", [])
    if not isinstance(news, list):
        raise SourceError("Source field 'news' must be an array when present")
    for index, item in enumerate(news):
        if not isinstance(item, dict):
            raise SourceError(f"news[{index}] must be an object")


def build_source(
    refresh_upstream: bool = False,
    write_output: bool = True,
) -> tuple[Path, int]:
    config = load_json(CONFIG_PATH)
    if not isinstance(config, dict):
        raise SourceError("config/source.json must contain an object")

    upstream_config = config.get("upstream")
    if not isinstance(upstream_config, dict):
        raise SourceError("config/source.json must contain an upstream object")

    cache_path = resolve_config_path(str(upstream_config["cache"]))
    if refresh_upstream:
        upstream = fetch_json(str(upstream_config["url"]))
        if write_output:
            write_json(cache_path, upstream)
    else:
        upstream = load_json(cache_path)
    if not isinstance(upstream, dict):
        raise SourceError("Upstream source root must be an object")

    extras = load_json(resolve_config_path(str(config["extras"])))
    if isinstance(extras, list):
        extra_apps: list[dict[str, Any]] = extras
        extra_news: list[dict[str, Any]] = []
    elif isinstance(extras, dict):
        extra_apps = extras.get("apps", [])
        extra_news = extras.get("news", [])
    else:
        raise SourceError("Extra apps file must contain an array or object")
    if not isinstance(extra_apps, list) or not isinstance(extra_news, list):
        raise SourceError("Extra apps file fields 'apps' and 'news' must be arrays")

    apps = selected_upstream_apps(upstream, upstream_config)
    apps = merge_by_bundle(apps, extra_apps)
    included_bundles = {app_identity(app) for app in apps}

    source_metadata = config.get("source")
    if not isinstance(source_metadata, dict):
        raise SourceError("config/source.json must contain a source object")
    source: dict[str, Any] = dict(source_metadata)
    source["apps"] = apps

    upstream_news = upstream.get("news", [])
    if not isinstance(upstream_news, list):
        raise SourceError("Upstream source field 'news' must be an array when present")
    news = merge_news(upstream_news, extra_news, included_bundles)
    if news:
        source["news"] = news
    else:
        source.pop("news", None)

    validate_source(source)
    output_path = resolve_config_path(str(config["output"]))
    if write_output:
        write_json(output_path, source)
    return output_path, len(apps)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh-upstream",
        action="store_true",
        help="Fetch the latest AltGallery source before building.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Build and validate the source without changing generated output.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        output_path, app_count = build_source(
            refresh_upstream=args.refresh_upstream,
            write_output=not args.check,
        )
    except (KeyError, SourceError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.check:
        print(f"Valid source: {app_count} app(s) -> {output_path}")
    else:
        print(f"Built source: {app_count} app(s) -> {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
