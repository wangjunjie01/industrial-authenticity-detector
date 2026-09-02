from pathlib import Path
import tempfile
import unittest

from industrial_authenticity.model import LightweightModel
from industrial_authenticity.private_corpus import PrivateCorpus


class PrivateCorpusTests(unittest.TestCase):
    def test_import_keeps_text_local_and_status_is_aggregate(self):
        with tempfile.TemporaryDirectory() as folder:
            corpus = PrivateCorpus(Path(folder))
            status = corpus.import_samples([{"category": "linkedin", "text": "A private industrial article about 5 mm dividers."}])
            self.assertEqual(status["sample_count"], 1)
            self.assertNotIn("text", status)
            self.assertFalse(status["sufficient"])
            validation = corpus.validate(LightweightModel.load(), LightweightModel.load())
            self.assertTrue(validation["allowed"])
            self.assertNotIn("A private", str(validation))

    def test_bad_category_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                PrivateCorpus(Path(folder)).import_samples([{"category": "email", "text": "secret"}])


if __name__ == "__main__":
    unittest.main()
