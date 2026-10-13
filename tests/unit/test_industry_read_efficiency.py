"""Domain projection reads do not duplicate the source ledger or copy history for identities."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from inresearch.knowledge import industry
from inresearch.delivery import source_publication as publication
from inresearch.storage.files import write_json
from inresearch.paths import project_root

class IndustryReadEfficiencyTests(unittest.TestCase):
    def test_snapshot_shares_one_runtime_read_across_directory_projects_and_updates(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ', {'INRESEARCH_RUNTIME_ROOT':tmp}):
            with patch.object(publication, 'state', wraps=publication.state) as read:
                result = industry.snapshot(project_root(), {'overview':'1'})
                self.assertTrue(result['rows'])
                self.assertGreater(result['research_updates']['total'],0)
                self.assertEqual(read.call_count,1)

    def test_company_directory_does_not_copy_or_validate_observation_payloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);write_json(root/'data/companies.json',{'records':[]})
            obj={'id':'company:one','type':'company','identity':{'company_id':'one'},'name':'One'}
            write_json(root/'data/object_observations.json',{'version':1,'objects':{},'records':[]})
            state={'objects':{'company:one':obj},'records':[{'irrelevant_history':object()}]}
            before=copy.deepcopy(obj)
            with patch.object(publication,'state',side_effect=AssertionError('no second runtime read')):
                result=publication.companies(root,runtime=state)
            self.assertEqual(result['records'][0]['company_id'],'one')
            self.assertEqual(obj,before)
