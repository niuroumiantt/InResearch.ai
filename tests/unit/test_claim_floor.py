import unittest

import test_continuous_reader as fixtures
from inresearch.workflow import reader as cr


class ClaimFloorTests(fixtures.ReaderTests):
    def two_docs(self, floor):
        self.reader.close()
        self.reader = cr.Reader(self.base / "data", self.base / "state", self.base / "repo", self.model, 0, 200,
                                self.clock, claim_min_priority=floor).initialize()
        self.put("low.txt", "低优先级资料：服务器功率 200 W。\n")
        self.put("high.txt", "高优先级资料：机柜功率 40 kW。\n")
        with self.reader.worker_session():
            self.reader.scan()
        with self.reader.transaction():
            self.reader.conn.execute("UPDATE reading_runs SET priority=CASE WHEN doc_id IN "
                                     "(SELECT doc_id FROM documents WHERE original_name='high.txt') THEN 9 ELSE 5 END")
        self.run_reader()
        return {r["original_name"]: r["state"] for r in self.reader.conn.execute("SELECT original_name,state FROM current_readings")}

    def test_documents_below_the_floor_wait_untouched(self):
        states = self.two_docs(7)
        self.assertEqual(states, {"high.txt": "complete", "low.txt": "queued"})
        low = self.reader.conn.execute("SELECT j.state,j.attempts FROM jobs j JOIN documents d USING(doc_id) "
                                       "WHERE d.original_name='low.txt'").fetchall()
        self.assertTrue(all(r["state"] == "pending" and r["attempts"] == 0 for r in low))
        self.assertEqual(self.reader.status()["claim_floor"], {"min_priority": 7, "held_documents": 1})

    def test_floor_zero_reads_everything(self):
        self.assertEqual(self.two_docs(0), {"high.txt": "complete", "low.txt": "complete"})

    def test_invalid_floor_is_refused(self):
        for bad in (-1, 11, "7", 7.0):
            with self.assertRaises(ValueError):
                cr.Reader(self.base / "d2", self.base / "s2", self.base / "repo", self.model, 0, 200, self.clock,
                          claim_min_priority=bad)


if __name__ == "__main__":
    unittest.main()
