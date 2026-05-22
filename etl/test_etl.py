import unittest
import os
import sys
import json
import shutil

# Set environment variables to point to test fixtures before importing ETL modules
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'tests', 'fixtures')
TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'tests', 'data_temp')

os.environ['KAIKKI_PATH'] = os.path.join(FIXTURES_DIR, 'sample_kaikki.jsonl')
os.environ['FREQUENCY_CSV_PATH'] = os.path.join(FIXTURES_DIR, 'sample_frequencies.csv')
os.environ['RAW_DBNARY_PATH'] = os.path.join(FIXTURES_DIR, 'sample_ontolex.ttl')
os.environ['DATA_DIR'] = TEST_DATA_DIR

# Create temp data directory
os.makedirs(TEST_DATA_DIR, exist_ok=True)

# Add parent directory to sys.path so we can import etl modules
sys.path.insert(0, os.path.dirname(__file__))

class TestUkrainianETL(unittest.TestCase):

    def setUp(self):
        # Clear temporary data dir before each test
        if os.path.exists(TEST_DATA_DIR):
            shutil.rmtree(TEST_DATA_DIR)
        os.makedirs(TEST_DATA_DIR, exist_ok=True)

    def tearDown(self):
        # Clean up temporary data dir
        if os.path.exists(TEST_DATA_DIR):
            shutil.rmtree(TEST_DATA_DIR)

    def test_pipeline_integration(self):
        # Import the modules here to ensure environment variables are applied first
        from ontolex import Ontolex
        from dictionary import Dictionary

        # 1. Parse Ontolex translations offline
        print("\n--- Running OntoLex Parser ---")
        o = Ontolex(use_cache=False, use_raw_cache=False)
        
        # Verify OntoLex parsed translations
        ontolex_dict = o.get_dict()
        self.assertIn("mati", ontolex_dict)
        self.assertIn("have", ontolex_dict)
        
        # 2. Get dictionary from OntoLex
        d = o.get_dictionary()
        
        # 3. Add Wiktionary/Kaikki JSONL words
        print("\n--- Adding Wiktionary Words ---")
        d.add_wiktionary_words()
        
        # Verify dictionary word entries
        self.assertIn("ма́ти", d.dict)
        self.assertIn("за́мок", d.dict)
        self.assertIn("замо́к", d.dict)
        
        # Verify homograph division
        mati_word = d.dict["ма́ти"]
        self.assertIn("noun", mati_word.usages)
        self.assertIn("verb", mati_word.usages)
        
        # Verify frequencies were mapped from CSV
        noun_usage = mati_word.usages["noun"]
        self.assertEqual(noun_usage.frequency, 1)
        verb_usage = mati_word.usages["verb"]
        self.assertEqual(verb_usage.frequency, 2)

        # 4. Dump files
        dict_json_path = os.path.join(TEST_DATA_DIR, 'dictionary_data.json')
        index_json_path = os.path.join(TEST_DATA_DIR, 'index.json')
        word_dict_json_path = os.path.join(TEST_DATA_DIR, 'word_dict.json')

        d.dump(dict_json_path, indent=4, final_form=True)
        d.make_index(index_json_path, word_dict_json_path, indent=4)

        # Verify output files exist and are valid JSON
        self.assertTrue(os.path.exists(dict_json_path))
        self.assertTrue(os.path.exists(index_json_path))
        self.assertTrue(os.path.exists(word_dict_json_path))

        with open(dict_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.assertGreater(len(data), 0)
            # Ensure all dictionary listings have required keys
            for item in data:
                self.assertIn("word", item)
                self.assertIn("pos", item)
                self.assertIn("defs", item)
                self.assertIn("freq", item)

if __name__ == '__main__':
    unittest.main()
