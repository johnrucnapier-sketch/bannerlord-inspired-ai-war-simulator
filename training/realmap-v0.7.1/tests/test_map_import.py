import json,tempfile,unittest
from pathlib import Path
from tools.make_test_map import generate
from tools.import_map import validate

class MapImport(unittest.TestCase):
    def test_original_fixture_validates(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'map';generate(p);self.assertEqual(len(validate(p)['clans.json']),18)
    def test_broken_adjacency_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'map';generate(p);f=p/'navigation.json';d=json.loads(f.read_text());d['faces'][0]['neighbors']=[999999];f.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,'adjacency'):validate(p)
    def test_wrong_village_binding_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'map';generate(p);f=p/'settlements.json';d=json.loads(f.read_text());next(x for x in d if x['kind']=='village')['parent_city']='no-such-city';f.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,'binding'):validate(p)
if __name__=='__main__':unittest.main()
