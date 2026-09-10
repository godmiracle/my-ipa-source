import importlib.util
import unittest


SPEC = importlib.util.spec_from_file_location(
    "build_source", "scripts/build_source.py"
)
assert SPEC and SPEC.loader
build_source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_source)


class BuildSourceTests(unittest.TestCase):
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
