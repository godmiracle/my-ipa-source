#!/usr/bin/env python3
"""Build a personal AltStore source for LiveContainer.

The generated all-apps.json is composed from a cached upstream source,
GitHub-Releases-managed apps, and user-maintained extra app/news entries. The
script intentionally uses only the Python standard library so it can run in
GitHub Actions without dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
import re
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


def fetch_json(url: str, headers: dict[str, str] | None = None) -> Any:
    request_headers = {
        "Accept": "application/json",
        "User-Agent": "personal-livecontainer-source/1.0",
    }
    if headers:
        request_headers.update(headers)
    request = Request(
        url,
        headers=request_headers,
    )
    try:
        with urlopen(request, timeout=60) as response:
            payload = response.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise SourceError(f"Unable to fetch JSON {url}: {exc}") from exc

    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceError(f"Response is not valid UTF-8 JSON: {url}") from exc


def app_identity(app: dict[str, Any]) -> str:
    return str(app.get("bundleIdentifier", ""))


def load_github_release_definitions(path: Path) -> list[dict[str, Any]]:
    """Load and validate app definitions backed by GitHub Releases."""
    value = load_json(path)
    if isinstance(value, list):
        definitions = value
    elif isinstance(value, dict):
        definitions = value.get("apps", [])
    else:
        raise SourceError(
            "GitHub Releases config must contain an array or an object with an apps array"
        )
    if not isinstance(definitions, list):
        raise SourceError("GitHub Releases config field 'apps' must be an array")

    for index, definition in enumerate(definitions):
        if not isinstance(definition, dict):
            raise SourceError(f"githubReleases.apps[{index}] must be an object")
        for key in ("name", "bundleIdentifier", "github"):
            if key not in definition:
                raise SourceError(f"githubReleases.apps[{index}] is missing {key}")

        github = definition["github"]
        if not isinstance(github, dict):
            raise SourceError(f"githubReleases.apps[{index}].github must be an object")
        repo = github.get("repo")
        if (
            not isinstance(repo, str)
            or not repo.strip()
            or not re.fullmatch(r"[^/\s]+/[^/\s]+", repo.strip())
        ):
            raise SourceError(
                f"githubReleases.apps[{index}].github.repo must use OWNER/REPOSITORY format"
            )
        asset_pattern = github.get("assetPattern")
        if not isinstance(asset_pattern, str) or not asset_pattern:
            raise SourceError(
                f"githubReleases.apps[{index}].github.assetPattern must be a non-empty string"
            )
        try:
            re.compile(asset_pattern)
        except re.error as exc:
            raise SourceError(
                f"githubReleases.apps[{index}].github.assetPattern is invalid: {exc}"
            ) from exc

        include_prereleases = github.get("includePrereleases", False)
        if not isinstance(include_prereleases, bool):
            raise SourceError(
                f"githubReleases.apps[{index}].github.includePrereleases must be boolean"
            )
        strip_tag_prefix = github.get("stripTagPrefix", "v")
        if not isinstance(strip_tag_prefix, str):
            raise SourceError(
                f"githubReleases.apps[{index}].github.stripTagPrefix must be a string"
            )
        max_versions = github.get("maxVersions", 1)
        if (
            not isinstance(max_versions, int)
            or isinstance(max_versions, bool)
            or max_versions < 1
        ):
            raise SourceError(
                f"githubReleases.apps[{index}].github.maxVersions must be a positive integer"
            )

        bundle = definition.get("bundleIdentifier")
        if not isinstance(bundle, str) or not bundle.strip():
            raise SourceError(
                f"githubReleases.apps[{index}].bundleIdentifier must be a non-empty string"
            )
        min_os_version = definition.get("minOSVersion")
        if min_os_version is not None and not isinstance(min_os_version, str):
            raise SourceError(
                f"githubReleases.apps[{index}].minOSVersion must be a string when present"
            )
    return definitions


def github_releases_url(repo: str) -> str:
    return f"https://api.github.com/repos/{repo}/releases?per_page=100"


def fetch_github_releases(repo: str) -> list[dict[str, Any]]:
    """Fetch releases for a public GitHub repository."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    value = fetch_json(github_releases_url(repo), headers=headers)
    if not isinstance(value, list):
        raise SourceError(f"GitHub Releases response for {repo} must be an array")
    for index, release in enumerate(value):
        if not isinstance(release, dict):
            raise SourceError(f"GitHub release {repo}[{index}] must be an object")
    return value


def load_github_release_cache(path: Path) -> dict[str, Any]:
    value = load_json(path)
    if not isinstance(value, dict):
        raise SourceError("GitHub Releases cache root must be an object")
    repositories = value.get("repositories")
    if not isinstance(repositories, dict):
        raise SourceError("GitHub Releases cache field 'repositories' must be an object")
    return value


def refresh_github_release_cache(
    definitions: list[dict[str, Any]],
    cache_path: Path,
    write_output: bool,
) -> dict[str, Any]:
    """Fetch each configured repository once and cache only usable releases."""
    repositories: dict[str, Any] = {}
    fetched: dict[str, list[dict[str, Any]]] = {}
    for definition in definitions:
        github = definition["github"]
        repo = str(github["repo"]).strip()
        if repo not in fetched:
            fetched[repo] = fetch_github_releases(repo)

        candidates = matching_github_release_assets(definition, fetched[repo])
        max_versions = int(github.get("maxVersions", 1))
        selected: dict[str, dict[str, Any]] = {
            release_cache_identity(release): compact_github_release(release)
            for release, _asset in candidates[:max_versions]
        }
        if not selected:
            pattern = github["assetPattern"]
            raise SourceError(
                f"No matching GitHub Release IPA found for {repo} with assetPattern {pattern!r}"
            )
        existing = repositories.setdefault(repo, {"releases": {}})
        cached_by_identity = existing["releases"]
        cached_by_identity.update(selected)

    for repository in repositories.values():
        repository["releases"] = list(repository["releases"].values())

    cache: dict[str, Any] = {"repositories": repositories}
    if write_output:
        write_json(cache_path, cache)
    return cache


def cached_releases(cache: dict[str, Any], repo: str) -> list[dict[str, Any]]:
    repositories = cache["repositories"]
    entry = repositories.get(repo)
    if not isinstance(entry, dict):
        raise SourceError(
            f"GitHub Releases cache has no entry for {repo}; run with --refresh-upstream"
        )
    releases = entry.get("releases")
    if not isinstance(releases, list):
        raise SourceError(f"GitHub Releases cache entry for {repo} must contain releases")
    for index, release in enumerate(releases):
        if not isinstance(release, dict):
            raise SourceError(f"GitHub release cache {repo}[{index}] must be an object")
    return releases


def release_sort_key(release: dict[str, Any]) -> str:
    return str(release.get("published_at") or release.get("created_at") or "")


def release_cache_identity(release: dict[str, Any]) -> str:
    return str(release.get("id") or release.get("tag_name") or release_sort_key(release))


def compact_github_release(release: dict[str, Any]) -> dict[str, Any]:
    """Keep the cache small while retaining fields needed to rebuild the source."""
    compact: dict[str, Any] = {}
    for key in ("id", "tag_name", "published_at", "created_at", "prerelease", "draft", "body"):
        if key in release:
            compact[key] = release[key]

    assets = release.get("assets", [])
    compact["assets"] = []
    if isinstance(assets, list):
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            compact_asset = {
                key: asset[key]
                for key in ("name", "browser_download_url", "size")
                if key in asset
            }
            compact["assets"].append(compact_asset)
    return compact


def matching_github_release_assets(
    definition: dict[str, Any], releases: list[dict[str, Any]]
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Return releases and their first matching asset, newest first."""
    github = definition["github"]
    asset_pattern = re.compile(str(github["assetPattern"]))
    include_prereleases = bool(github.get("includePrereleases", False))

    candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for release in sorted(releases, key=release_sort_key, reverse=True):
        if release.get("draft") is True:
            continue
        if release.get("prerelease") is True and not include_prereleases:
            continue

        tag_name = str(release.get("tag_name") or "").strip()
        if not tag_name:
            continue
        assets = release.get("assets", [])
        if not isinstance(assets, list):
            continue
        matching_assets = [
            asset
            for asset in assets
            if isinstance(asset, dict)
            and asset_pattern.search(str(asset.get("name") or ""))
        ]
        if matching_assets:
            candidates.append((release, matching_assets[0]))
    return candidates


def build_github_release_app(
    definition: dict[str, Any], releases: list[dict[str, Any]]
) -> dict[str, Any]:
    """Turn the newest matching GitHub release assets into an AltStore app."""
    github = definition["github"]
    repo = str(github["repo"]).strip()
    strip_tag_prefix = str(github.get("stripTagPrefix", "v"))
    max_versions = int(github.get("maxVersions", 1))

    versions: list[dict[str, Any]] = []
    candidates = matching_github_release_assets(definition, releases)
    for release, asset in candidates[:max_versions]:
        tag_name = str(release.get("tag_name") or "").strip()
        download_url = asset.get("browser_download_url")
        if not isinstance(download_url, str) or not download_url.startswith("https://"):
            raise SourceError(
                f"GitHub release asset for {repo} does not have an HTTPS download URL"
            )

        version_name = tag_name
        if strip_tag_prefix and version_name.startswith(strip_tag_prefix):
            version_name = version_name[len(strip_tag_prefix) :]
        if not version_name:
            raise SourceError(f"GitHub release tag for {repo} produced an empty version")

        version: dict[str, Any] = {
            "version": version_name,
            "downloadURL": download_url,
        }
        release_date = release.get("published_at") or release.get("created_at")
        if isinstance(release_date, str) and release_date:
            version["date"] = release_date
        release_body = release.get("body")
        if isinstance(release_body, str) and release_body.strip():
            version["localizedDescription"] = release_body
        asset_size = asset.get("size")
        if isinstance(asset_size, int) and not isinstance(asset_size, bool):
            version["size"] = asset_size

        min_os_version = definition.get("minOSVersion")
        if isinstance(min_os_version, str) and min_os_version.strip():
            version["minOSVersion"] = min_os_version
        build_version = definition.get("buildVersion")
        if isinstance(build_version, str) and build_version.strip():
            version["buildVersion"] = build_version

        versions.append(version)
        if len(versions) >= max_versions:
            break

    if not versions:
        pattern = github["assetPattern"]
        raise SourceError(
            f"No matching GitHub Release IPA found for {repo} with assetPattern {pattern!r}"
        )

    app = {
        key: value
        for key, value in definition.items()
        if key not in {"github", "minOSVersion", "buildVersion"}
    }
    app["versions"] = versions
    return app


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

    github_release_apps: list[dict[str, Any]] = []
    github_releases_config = config.get("githubReleases")
    if github_releases_config is not None:
        if not isinstance(github_releases_config, dict):
            raise SourceError("config/source.json field 'githubReleases' must be an object")
        definitions_path = resolve_config_path(str(github_releases_config["config"]))
        cache_path = resolve_config_path(str(github_releases_config["cache"]))
        definitions = load_github_release_definitions(definitions_path)
        if refresh_upstream:
            github_cache = refresh_github_release_cache(
                definitions,
                cache_path,
                write_output=write_output,
            )
        elif definitions:
            github_cache = load_github_release_cache(cache_path)
        else:
            github_cache = {"repositories": {}}

        for definition in definitions:
            github = definition["github"]
            repo = str(github["repo"]).strip()
            github_release_apps.append(
                build_github_release_app(
                    definition,
                    cached_releases(github_cache, repo),
                )
            )

    apps = selected_upstream_apps(upstream, upstream_config)
    apps = merge_by_bundle(apps, github_release_apps)
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
        "--refresh",
        action="store_true",
        help="Fetch the latest AltGallery source and configured GitHub Releases before building.",
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
