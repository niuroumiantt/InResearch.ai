import unittest

import test_continuous_reader as fixtures
from inresearch.adapters import models, reader_model
from inresearch.materials import reader_contracts


class Raising:
    def __init__(self, code):
        self.code = code

    def generate(self, system, user, **kwargs):
        raise models.InferenceError(self.code)


class CallMappingTests(unittest.TestCase):
    def mapped(self, code):
        try:
            reader_model.ModelClient._call(Raising(code), "s", "u")
        except reader_contracts.ReaderError as exc:
            return type(exc), exc.code

    def test_transient_cli_exits_are_retryable_and_keep_their_code(self):
        for code in ("model_cli_failed", "model_cli_timeout", "model_cli_output_limit"):
            kind, recorded = self.mapped(code)
            self.assertTrue(issubclass(kind, reader_contracts.ModelError), code)
            self.assertFalse(issubclass(kind, reader_contracts.Blocked), code)
            self.assertEqual(recorded, code)

    def test_setup_errors_still_block(self):
        for code in ("model_cli_authentication_failed", "model_cli_not_installed", "model_identity_unverified"):
            self.assertEqual(self.mapped(code), (reader_contracts.Blocked, code))
        self.assertEqual(self.mapped("model_failure"), (reader_contracts.ModelError, "model_failure"))


class FlakyCli(fixtures.Model):
    """The first read call fails the way an overloaded Claude CLI does."""
    def __init__(self):
        super().__init__()
        self.failed = False

    def generate(self, stage, payload, retry_instruction=None):
        if stage == "read" and not self.failed:
            self.failed = True
            raise reader_contracts.TransientModelError("model_cli_failed")
        return super().generate(stage, payload, retry_instruction)


class ReaderRetryTests(fixtures.ReaderTests):
    def test_a_transient_cli_failure_is_retried_and_the_document_completes(self):
        self.model = FlakyCli()
        self.reader.close()
        self.reader = self.make_reader()
        self.register()
        self.run_reader()
        job = self.reader.conn.execute("SELECT state,error_code,attempts FROM jobs WHERE stage='read'").fetchone()
        self.assertEqual((job["state"], job["error_code"]), ("pending", "model_cli_failed"))
        self.assertNotEqual(self.first_doc()["state"], "blocked")
        self.clock.advance(31)
        self.run_reader()
        self.assertEqual(self.first_doc()["state"], "complete")


if __name__ == "__main__":
    unittest.main()
