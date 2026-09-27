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

    def test_content_fields_stay_required(self):
        read = reader_model._schema("read")
        self.assertEqual(read["required"], ["chunk_sha256", "summary", "claims"])
        self.assertEqual(read["properties"]["claims"]["items"]["required"], ["text", "kind", "evidence"])
        self.assertEqual(reader_model._schema("triage")["required"], ["classification", "importance", "rationale"])


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
