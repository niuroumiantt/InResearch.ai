import unittest

from inresearch.adapters import models


class DefaultModelRoleTests(unittest.TestCase):
    """The shipped deploy/models.json assigns each role the model 08 names for it."""

    def test_research_default_is_sonnet_through_claude_cli(self):
        profile = models.load_profile("research_default", models.DEFAULT_CONFIG)
        self.assertEqual((profile.backend, profile.model), ("claude_cli", "claude-sonnet-5"))

    def test_core_review_is_opus_through_claude_cli(self):
        profile = models.load_profile("core_review", models.DEFAULT_CONFIG)
        self.assertEqual((profile.backend, profile.model), ("claude_cli", "claude-opus-5-5"))

    def test_ocr_stays_unconfigured_by_default_and_spark_profiles_validate(self):
        with self.assertRaisesRegex(models.InferenceError, "model_role_not_configured:ocr"):
            models.load_profile("ocr", models.DEFAULT_CONFIG)
        import json
        profiles = json.loads(models.DEFAULT_CONFIG.read_text(encoding="utf-8"))["profiles"]
        self.assertEqual(models.ModelProfile(**profiles["spark_ocr"]).capabilities, ("vision_json",))
        self.assertEqual(models.ModelProfile(**profiles["spark"]).model, "qwen3.8:27b")


if __name__ == "__main__":
    unittest.main()
