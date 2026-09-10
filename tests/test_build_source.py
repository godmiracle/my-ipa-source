import importlib.util
import unittest


SPEC = importlib.util.spec_from_file_location(
    "build_source", "scripts/build_source.py"
)
assert SPEC and SPEC.loader
build_source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_source)


class BuildSourceTests(unittest.TestCase):
    def test_github_release_app_selects_latest_matching_stable_ipa(self):
        definition = {
            "name": "Example",
            "bundleIdentifier": "com.example.app",
            "developerName": "Example Dev",
            "subtitle": "Example",
            "minOSVersion": "13.0",
            "github": {
                "repo": "owner/example",
                "assetPattern": ".*ios.*\\.ipa$",
                "includePrereleases": False,
                "stripTagPrefix": "v",
            },
        }
        releases = [
            {
                "tag_name": "v2.0.0-beta.1",
                "published_at": "2026-09-10T00:00:00Z",
                "prerelease": True,
                "assets": [
                    {
                        "name": "Example-ios.ipa",
                        "browser_download_url": "https://example.com/beta.ipa",
                        "size": 200,
                    }
                ],
            },
            {
                "tag_name": "v1.2.0",
                "published_at": "2026-09-01T00:00:00Z",
                "prerelease": False,
                "body": "Release notes",
                "assets": [
                    {
                        "name": "Example-ios.ipa",
                        "browser_download_url": "https://example.com/1.2.0.ipa",
                        "size": 100,
                    },
                    {
                        "name": "Example-macos.zip",
                        "browser_download_url": "https://example.com/macos.zip",
                        "size": 300,
                    },
                ],
            },
        ]

        result = build_source.build_github_release_app(definition, releases)

        self.assertEqual(result["versions"][0]["version"], "1.2.0")
        self.assertEqual(
            result["versions"][0]["downloadURL"],
            "https://example.com/1.2.0.ipa",
        )
        self.assertEqual(result["versions"][0]["minOSVersion"], "13.0")
        self.assertEqual(result["versions"][0]["size"], 100)
        self.assertNotIn("github", result)

    def test_github_release_app_can_include_prerelease(self):
        definition = {
            "name": "Nightly",
            "bundleIdentifier": "com.example.nightly",
            "minOSVersion": "15.0",
            "github": {
                "repo": "owner/nightly",
                "assetPattern": "\\.ipa$",
                "includePrereleases": True,
                "stripTagPrefix": "",
            },
        }
        releases = [
            {
                "tag_name": "nightly-20260910",
                "published_at": "2026-09-10T00:00:00Z",
                "prerelease": True,
                "assets": [
                    {
                        "name": "nightly.ipa",
                        "browser_download_url": "https://example.com/nightly.ipa",
                    }
                ],
            }
        ]

        result = build_source.build_github_release_app(definition, releases)

        self.assertEqual(result["versions"][0]["version"], "nightly-20260910")

    def test_extra_app_replaces_same_bundle_identifier(self):
        upstream = [
            {
                "name": "Original",
                "bundleIdentifier": "com.example.app",
                "versions": [{"version": "1.0", "downloadURL": "https://example.com/1.ipa"}],
            }
        ]
        extra = {
            "name": "Personal Variant",
            "bundleIdentifier": "com.example.app",
            "versions": [{"version": "2.0", "downloadURL": "https://example.com/2.ipa"}],
        }

        result = build_source.merge_by_bundle(upstream, [extra])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Personal Variant")
        self.assertEqual(result[0]["versions"][0]["version"], "2.0")

    def test_extra_app_is_appended(self):
        result = build_source.merge_by_bundle(
            [],
            [
                {
                    "name": "Extra",
                    "bundleIdentifier": "com.example.extra",
                    "versions": [
                        {"version": "1.0", "downloadURL": "https://example.com/extra.ipa"}
                    ],
                }
            ],
        )
        self.assertEqual([app["name"] for app in result], ["Extra"])

    def test_invalid_download_url_is_rejected(self):
        with self.assertRaises(build_source.SourceError):
            build_source.validate_source(
                {
                    "name": "Source",
                    "apps": [
                        {
                            "name": "Bad",
                            "bundleIdentifier": "com.example.bad",
                            "versions": [
                                {"version": "1.0", "downloadURL": "http://example.com/a.ipa"}
                            ],
                        }
                    ],
                }
            )


if __name__ == "__main__":
    unittest.main()
