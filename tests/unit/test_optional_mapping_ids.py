import unittest

import test_continuous_reader as fixtures
from inresearch.adapters import reader_model


def walk(schema):
    yield schema
    for value in schema.get("properties", {}).values():
        yield from walk(value)
    if isinstance(schema.get("items"), dict):
        yield from walk(schema["items"])


class SchemaTests(unittest.TestCase):
    def test_mapping_ids_are_never_required(self):
        for stage in ("triage", "read", "synthesize"):
            for node in walk(reader_model._schema(stage)):
                self.assertFalse({"object_ids", "question_ids"} & set(node.get("required", [])), stage)

    def test_claims_come_before_the_summary(self):
        order = list(reader_model._schema("read")["properties"])
        self.assertLess(order.index("claims"), order.index("summary"))

    def test_content_fields_stay_required(self):
        read = reader_model._schema("read")
        self.assertEqual(read["required"], ["chunk_sha256", "claims", "summary"])
        self.assertEqual(read["properties"]["claims"]["items"]["required"], ["text", "kind", "evidence"])
        self.assertEqual(reader_model._schema("triage")["required"], ["classification", "importance", "rationale"])


class PromptTests(unittest.TestCase):
    def test_read_prompt_states_the_summary_limit_and_the_required_fields(self):
        seen = {}

        class Recorder:
            def generate(self, system, user, **kwargs):
                seen["system"] = system
                return {}
        client = reader_model.ModelClient.__new__(reader_model.ModelClient)
        client.client = Recorder()
        client.generate("read", {"x": 1})
        self.assertIn("within 1200 characters", seen["system"])
        self.assertIn("THIS chunk only", seen["system"])
        self.assertIn("claims as [] when there is none", seen["system"])
        self.assertIn("Write the claims first", seen["system"])
        self.assertNotIn("explain the document content", seen["system"])
        self.assertLess(seen["system"].index('"claims":['), seen["system"].index('"summary":'))


class NoIds(fixtures.Model):
    """Replies the way Sonnet sometimes does: the empty id arrays left out."""
    def generate(self, stage, payload, retry_instruction=None):
        out = super().generate(stage, payload, retry_instruction)
        out.pop("object_ids", None)
        out.pop("question_ids", None)
        for claim in out.get("claims", []):
            claim.pop("object_ids", None)
            claim.pop("question_ids", None)
        return out


class ReaderTests(fixtures.ReaderTests):
    def test_replies_without_id_arrays_complete_as_unmapped(self):
        self.model = NoIds()
        self.reader.close()
        self.reader = self.make_reader()
        self.register()
        self.run_reader()
        doc = self.first_doc()
        self.assertEqual(doc["state"], "complete")


if __name__ == "__main__":
    unittest.main()
