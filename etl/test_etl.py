import unittest
import os
import sys
import json
import shutil
from pathlib import Path

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
        o = Ontolex(use_cache=False, use_raw_cache=False, raw_dbnary_path=os.environ['RAW_DBNARY_PATH'])
        
        # Verify OntoLex parsed translations
        ontolex_dict = o.get_dict()
        self.assertIn("mati", ontolex_dict)
        self.assertIn("have", ontolex_dict)
        
        # 2. Get dictionary from OntoLex
        d = o.get_dictionary(
            kaikki_path=os.environ['KAIKKI_PATH'],
            frequency_csv_path=os.environ['FREQUENCY_CSV_PATH'],
        )
        
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

        words_json_path = os.path.join(TEST_DATA_DIR, 'words.json')
        with open(words_json_path, 'w', encoding='utf-8') as f:
            json.dump(d.get_final_forms(), f, ensure_ascii=False)

        # Verify output files exist and are valid JSON
        self.assertTrue(os.path.exists(dict_json_path))
        self.assertTrue(os.path.exists(index_json_path))
        self.assertTrue(os.path.exists(word_dict_json_path))
        self.assertTrue(os.path.exists(words_json_path))

        with open(dict_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.assertGreater(len(data), 0)
            # Ensure all dictionary listings have required keys
            for item in data:
                self.assertIn("word", item)
                self.assertIn("pos", item)
                self.assertIn("defs", item)
                self.assertIn("freq", item)

        with open(words_json_path, 'r', encoding='utf-8') as f:
            word_entries = json.load(f)
            self.assertGreater(len(word_entries), 0)
            self.assertTrue(all('word' in item and 'pos' in item for item in word_entries))

    def test_verb_counterparts_are_embedded_into_final_forms(self):
        from build_verb_aspect_map import build_verb_counterpart_map, annotate_words_with_counterparts

        words = [
            {'word': 'співати', 'pos': 'verb', 'freq': 1, 'index': 0},
            {'word': 'заспівати', 'pos': 'verb', 'freq': 2, 'index': 1},
        ]

        sample_jsonl = Path(TEST_DATA_DIR) / 'sample_verb_pairs.jsonl'
        sample_jsonl.write_text(
            json.dumps({
                'pos': 'verb',
                'word': 'співати',
                'forms': [
                    {
                        'tags': ['perfective'],
                        'links': [['заспівати']],
                    },
                ],
            }) + '\n',
            encoding='utf-8',
        )

        mapping = build_verb_counterpart_map(words, sample_jsonl)
        annotate_words_with_counterparts(words, mapping)

        self.assertEqual(words[0]['counterparts'], [1])
        self.assertEqual(words[1]['counterparts'], [0])

    def test_verb_aspect_candidate_pairs_are_preserved(self):
        import extract

        sample_jsonl = Path(TEST_DATA_DIR) / 'sample_verb_aspect_candidates.jsonl'
        sample_jsonl.write_text(
            json.dumps({
                'pos': 'verb',
                'lang': 'Ukrainian',
                'lang_code': 'uk',
                'word': 'співати',
                'forms': [
                    {'form': 'співати', 'tags': ['canonical', 'imperfective']},
                    {'form': 'заспівати', 'tags': ['perfective'], 'links': [['заспівати']]},
                    {'form': 'співа́ти', 'tags': ['imperfective'], 'links': [['співа́ти']]},
                ],
            }) + '\n',
            encoding='utf-8',
        )

        words, aspect_pairs = extract.load_wiktionary_jsonl(sample_jsonl, return_aspect_candidates=True)
        self.assertEqual(aspect_pairs, {('співати', 'заспівати')})

    def test_inflection_lookup_missing_entry_preserves_usage(self):
        import extract
        import dictionary
        Word = dictionary.Word

        word = Word('тезаурус')
        word.add_definition('noun', 'thesaurus')
        results = extract.get_inflection(word, os.environ['KAIKKI_PATH'])

        self.assertEqual(results, [[None, None, None, None]])

        usage = word.usages['noun']
        needs_inflection, new_usages = usage.add_inflection(results)

        self.assertFalse(usage.delete_me)
        self.assertFalse(needs_inflection)
        self.assertEqual(new_usages, [])

    def test_add_inflection_does_not_apply_mismatched_pos_forms(self):
        import dictionary

        word = dictionary.Word('зеле́ний')
        word.add_definition('noun', 'green (colour)')
        usage = word.usages['noun']

        results = [[
            'зеле́ний',
            'adjective',
            {'nom am': ['зеле́ний']},
            'adj'
        ]]

        needs_inflection, new_usages = usage.add_inflection(results)

        self.assertEqual(usage.get_forms(), {})
        self.assertEqual(usage.definitions, {'green (colour)': None})
        self.assertEqual(new_usages, [])

    def test_load_wiktionary_jsonl_preserves_forms_info_and_alerts(self):
        import extract

        jsonl_path = os.path.join(FIXTURES_DIR, 'kaikki_load_wiktionary_forms.jsonl')
        words = extract.load_wiktionary_jsonl(jsonl_path)
        self.assertEqual(len(words), 1)
        word = words[0]
        self.assertEqual(word.word, 'Ка́нберра')
        self.assertIn('noun', word.usages)
        usage = word.usages['noun']
        self.assertIn('Canberra (the capital city of Australia) (proper noun)', usage.get_definitions())
        self.assertIn('nom ns', usage.get_forms())
        self.assertEqual(usage.get_forms()['nom ns'], ['Ка́нберра'])
        self.assertIn('gen ns', usage.get_forms())
        self.assertEqual(usage.get_forms()['gen ns'], ['Ка́нберри'])

    def test_parse_kaikki_entry_preserves_multiple_canonical_variants(self):
        import extract

        entry = {
            'word': 'зокрема',
            'lang': 'Ukrainian',
            'pos': 'adv',
            'forms': [
                {'form': 'зокре́ма', 'tags': ['canonical']},
                {'form': 'зокрема́', 'tags': ['canonical']},
                {'form': 'zokréma', 'tags': ['romanization']},
            ],
            'senses': [
                {'glosses': ['in particular']}
            ]
        }

        parsed = extract._parse_kaikki_entry(entry)
        self.assertIsInstance(parsed, dict)
        self.assertEqual(parsed['word'], 'зокре́ма')
        self.assertEqual(parsed['pos'], 'adverb')
        self.assertEqual(parsed['variants'], ['зокрема́'])
        self.assertNotIn('зокрема', [parsed['word'], *parsed['variants']])

    def test_parse_kaikki_entry_allows_form_for_multiple_adjective_genders(self):
        import extract

        entry = {
            'word': 'Є́льський',
            'lang': 'Ukrainian',
            'pos': 'adj',
            'forms': [
                {
                    'form': 'Є́льському',
                    'source': 'declension',
                    'tags': ['locative', 'masculine', 'neuter', 'singular']
                }
            ],
            'senses': [
                {'glosses': ['Yale']}
            ]
        }

        parsed = extract._parse_kaikki_entry(entry)
        if isinstance(parsed, list):
            parsed = parsed[0]
        self.assertIsInstance(parsed, dict)
        self.assertIn('loc am', parsed['forms'])
        self.assertIn('loc an', parsed['forms'])
        self.assertEqual(parsed['forms']['loc am'], ['Є́льському'])
        self.assertEqual(parsed['forms']['loc an'], ['Є́льському'])

    def test_usage_get_info_handles_masculine_inanimate_tags(self):
        import dictionary

        usage = dictionary.Usage('час', 'noun')
        usage.add_info({'gender': 'male', 'animacy': 'inanimate', 'aspect': None})

        self.assertEqual(usage.get_info(), 'male, inanimate')

    def test_parse_kaikki_entry_uses_sense_tags_for_info(self):
        import extract

        entry = {
            'word': 'час',
            'pos': 'noun',
            'forms': [
                {'form': 'час', 'tags': ['canonical']}
            ],
            'senses': [
                {'glosses': ['time'], 'tags': ['inanimate', 'masculine']}
            ]
        }

        parsed = extract._parse_kaikki_entry(entry)
        self.assertEqual(parsed['info']['gender'], 'male')
        self.assertEqual(parsed['info']['animacy'], 'inanimate')
        self.assertEqual(parsed['info']['aspect'], None)

    def test_form_of_word_is_removed_after_merge(self):
        import extract, dictionary

        source = Path(__file__).resolve().parent / 'sources' / 'kaikki.org-dictionary-Ukrainian.jsonl'
        parent = None
        entry = None
        with source.open('r', encoding='utf-8') as f:
            for line in f:
                if '"word": "допомога"' in line:
                    parent = json.loads(line)
                if '"word": "допомоги"' in line:
                    entry = json.loads(line)
                if parent and entry:
                    break

        self.assertIsNotNone(parent)
        self.assertIsNotNone(entry)

        parsed_parent = extract._parse_kaikki_entry(parent)
        parsed_entry = extract._parse_kaikki_entry(entry)

        D = dictionary.Dictionary(kaikki_path='kaikki', frequency_csv_path='freq')

        for p in (parsed_parent if isinstance(parsed_parent, list) else [parsed_parent]):
            w = dictionary.Word(p['word'])
            for d in p['definitions']:
                alert_value = d.get('metadata') if d.get('alert') else False
                w.add_definition(p['pos'], d['definition'], alert=alert_value)
            if p['forms']:
                w.add_forms(p['pos'], p['forms'], p['form_type'])
            D.add_to_dictionary(w)

        for p in (parsed_entry if isinstance(parsed_entry, list) else [parsed_entry]):
            w = dictionary.Word(p['word'])
            for d in p['definitions']:
                alert_value = d.get('metadata') if d.get('alert') else False
                w.add_definition(p['pos'], d['definition'], alert=alert_value)
            if p['forms']:
                w.add_forms(p['pos'], p['forms'], p['form_type'])
            D.add_to_dictionary(w)

        D.clean_alerted_words()
        D.garbage_collect()

        self.assertNotIn('допомоги', D.dict)
        self.assertIn('допомо́га', D.dict)
        self.assertIn('nom ns', D.dict['допомо́га'].usages['noun'].get_forms())

    def test_preserves_multiple_accent_variants(self):
        import dictionary

        d = dictionary.Dictionary(
            kaikki_path=os.environ['KAIKKI_PATH'],
            frequency_csv_path=os.environ['FREQUENCY_CSV_PATH']
        )

        word1 = dictionary.Word('зокре́ма')
        word1.add_definition('adverb', 'in particular')
        word2 = dictionary.Word('зокрема́')
        word2.add_definition('adverb', 'especially')

        d.add_to_dictionary(word1)
        d.add_to_dictionary(word2)

        self.assertIn('зокре́ма', d.dict)
        self.assertIn('зокрема́', d.dict)
        self.assertEqual(d.dict['зокре́ма'].get_word_no_accent(), d.dict['зокрема́'].get_word_no_accent())
        self.assertEqual(d.dict['зокре́ма'].usages['adverb'].get_definitions(), ['in particular'])
        self.assertEqual(d.dict['зокрема́'].usages['adverb'].get_definitions(), ['especially'])

    def test_merge_accentless_placeholder_into_accented_variant(self):
        import dictionary

        d = dictionary.Dictionary(kaikki_path='kaikki', frequency_csv_path='freq')

        accentless = dictionary.Word('Єльський')
        accentless.add_definition('adjective', 'test accentless')
        accentless.add_forms('adjective', {'nom am': ['Єльський'], 'dat am': ['Єльському'], 'voc am': ['Єльський']}, 'adj')

        accented = dictionary.Word('Є́льський')
        accented.add_definition('adjective', 'test accented')
        accented.add_forms('adjective', {'nom am': ['Є́льський'], 'dat am': ['Є́льському'], 'voc am': ['Є́льський']}, 'adj')

        d.add_to_dictionary(accentless)
        d.add_to_dictionary(accented)

        self.assertNotIn('Єльський', d.dict)
        self.assertIn('Є́льський', d.dict)
        self.assertTrue(d.dict['Є́льський'].usages['adjective'].get_forms())
        self.assertIn('dat am', d.dict['Є́льський'].usages['adjective'].get_forms())
        self.assertIn('voc am', d.dict['Є́льський'].usages['adjective'].get_forms())

    def test_merge_accentless_after_accented_variant(self):
        import dictionary

        d = dictionary.Dictionary(kaikki_path='kaikki', frequency_csv_path='freq')

        accented = dictionary.Word('Є́льський')
        accented.add_definition('adjective', 'test accented')
        accented.add_forms('adjective', {'nom am': ['Є́льський'], 'dat am': ['Є́льському'], 'voc am': ['Є́льський']}, 'adj')

        accentless = dictionary.Word('Єльський')
        accentless.add_definition('adjective', 'test accentless')
        accentless.add_forms('adjective', {'nom am': ['Єльський'], 'dat am': ['Єльському'], 'voc am': ['Єльський']}, 'adj')

        d.add_to_dictionary(accented)
        d.add_to_dictionary(accentless)

        self.assertNotIn('Єльський', d.dict)
        self.assertIn('Є́льський', d.dict)
        self.assertTrue(d.dict['Є́льський'].usages['adjective'].get_forms())
        self.assertIn('dat am', d.dict['Є́льський'].usages['adjective'].get_forms())
        self.assertIn('voc am', d.dict['Є́льський'].usages['adjective'].get_forms())

    def test_word_final_form_includes_variants(self):
        import dictionary

        word = dictionary.Word('зокре́ма')
        word.add_definition('adverb', 'in particular')
        word.add_variants(['зокрема́'])

        final_forms = word.get_final_form()
        self.assertEqual(len(final_forms), 1)
        self.assertEqual(final_forms[0]['variants'], ['зокрема́'])

    def test_drop_accentless_variant_when_accented_primary(self):
        import dictionary

        word = dictionary.Word('Украї́на')
        word.add_definition('noun', 'Ukraine')
        word.add_variants(['Україна'])

        final_forms = word.get_final_form()
        self.assertEqual(len(final_forms), 1)
        self.assertNotIn('variants', final_forms[0])

    def test_parse_kaikki_entry_alert_definition_flag(self):
        import extract

        jsonl_path = os.path.join(FIXTURES_DIR, 'kaikki_form_of.jsonl')
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            entry = json.loads(f.readline())

        parsed = extract._parse_kaikki_entry(entry)
        self.assertIsInstance(parsed, dict)
        self.assertEqual(len(parsed['definitions']), 1)
        self.assertIsInstance(parsed['definitions'][0], dict)
        self.assertTrue(parsed['definitions'][0]['alert'])
        self.assertEqual(parsed['definitions'][0]['definition'], 'locative singular of скасува́ння (skasuvánnja)')
        self.assertEqual(parsed['definitions'][0]['metadata']['relations'], ['form_of'])
        self.assertEqual(parsed['definitions'][0]['metadata']['targets'], ['скасува́ння'])
        self.assertIn('form-of', parsed['definitions'][0]['metadata']['tags'])
        self.assertNotIn('relation', parsed['definitions'][0]['metadata'])

    def test_parse_kaikki_entry_alt_of_relation_metadata(self):
        import extract

        jsonl_path = os.path.join(FIXTURES_DIR, 'kaikki_alt_of.jsonl')
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            entry = json.loads(f.readline())

        parsed = extract._parse_kaikki_entry(entry)
        self.assertTrue(parsed['definitions'][0]['alert'])
        self.assertEqual(parsed['definitions'][0]['metadata']['relations'], ['alt_of', 'abbreviation'])
        self.assertEqual(parsed['definitions'][0]['metadata']['targets'], ['Петро'])
        self.assertIn('alt-of', parsed['definitions'][0]['metadata']['tags'])
        self.assertNotIn('relation', parsed['definitions'][0]['metadata'])

    def test_parse_kaikki_entry_skips_related_derived_candidates(self):
        import extract

        entry = {
            'word': 'допомога',
            'pos': 'noun',
            'senses': [{'glosses': ['help, assistance, aid']}],
            'forms': [{'form': 'допомога', 'tags': ['canonical']}],
            'related': [{'word': 'допомогти́', 'tags': ['perfective']}],
        }

        parsed = extract._parse_kaikki_entry(entry)
        self.assertIsInstance(parsed, list)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]['word'], 'допомога')
        self.assertEqual(parsed[0]['pos'], 'noun')
        self.assertEqual(len(parsed[0]['definitions']), 1)
        self.assertEqual(parsed[1]['word'], 'допомогти́')
        self.assertEqual(parsed[1]['pos'], 'noun')
        self.assertEqual(parsed[1]['forms'], None)
        self.assertEqual(parsed[1]['form_type'], None)

    def test_parse_kaikki_entry_multiple_relation_metadata(self):
        import extract

        relation_jsonl = os.path.join(FIXTURES_DIR, 'relation_metadata.jsonl')
        with open(relation_jsonl, 'r', encoding='utf-8') as f:
            entry = json.loads(f.readline())

        parsed = extract._parse_kaikki_entry(entry)
        self.assertTrue(parsed['definitions'][0]['alert'])
        self.assertEqual(parsed['definitions'][0]['metadata']['relations'], ['alt_of', 'abbreviation'])
        self.assertEqual(parsed['definitions'][0]['metadata']['targets'], ['година'])
        self.assertIn('alt-of', parsed['definitions'][0]['metadata']['tags'])
        self.assertIn('abbreviation', parsed['definitions'][0]['metadata']['tags'])

    def test_parse_kaikki_entry_extracts_adjective_additional_forms(self):
        import extract

        entry = {
            'word': 'зелений',
            'pos': 'adj',
            'senses': [{'glosses': ['green']}],
            'forms': [
                {'form': 'зелений', 'tags': ['canonical']},
                {'form': 'зеленіший', 'tags': ['comparative']},
                {'form': 'найзеленіший', 'tags': ['superlative']},
            ]
        }

        parsed = extract._parse_kaikki_entry(entry)
        self.assertIsInstance(parsed, dict)
        self.assertEqual(parsed['word'], 'зелений')
        self.assertEqual(parsed['pos'], 'adjective')
        self.assertIn('addl comp', parsed['forms'])
        self.assertIn('addl super', parsed['forms'])
        self.assertEqual(parsed['forms']['addl comp'], ['зеленіший'])
        self.assertEqual(parsed['forms']['addl super'], ['найзеленіший'])

    def test_clean_alerted_words_resolves_form_of_metadata(self):
        import dictionary

        base = dictionary.Word('скасува́ння')
        base.add_definition('noun', 'cancellation')
        base.add_forms('noun', {'loc sg': ['скасува́нні']}, 'noun')

        alerted_usage = dictionary.Usage('скасува́нні', 'noun')
        alerted_metadata = {
            'relations': ['form_of'],
            'targets': ['скасува́ння'],
            'tags': ['form-of', 'locative', 'singular']
        }
        alerted_usage.add_definition('locative singular of скасува́ння (skasuvánnja)', alert=alerted_metadata)

        d = dictionary.Dictionary(
            kaikki_path=os.environ['KAIKKI_PATH'],
            frequency_csv_path=os.environ['FREQUENCY_CSV_PATH']
        )
        d.dict[base.word] = base
        d.accentless_words[base.get_word_no_accent()].add(base.word)

        alerted_usage.clean_alerted_words(d)
        self.assertEqual(alerted_usage.get_definitions(accept_alerts=True), [])
        self.assertEqual(alerted_usage.alerted_definitions, {})

    def test_clean_alerted_words_preserves_form_of_when_lemma_forms_missing(self):
        import dictionary

        lemma = dictionary.Word('скасува́ння')
        lemma.add_definition('noun', 'cancellation')

        alerted_usage = dictionary.Usage('скасува́нні', 'noun')
        alerted_metadata = {
            'relations': ['form_of'],
            'targets': ['скасува́ння'],
            'tags': ['form-of', 'locative', 'singular']
        }
        alerted_usage.add_definition('locative singular of скасува́ння (skasuvánnja)', alert=alerted_metadata)

        d = dictionary.Dictionary(
            kaikki_path=os.environ['KAIKKI_PATH'],
            frequency_csv_path=os.environ['FREQUENCY_CSV_PATH']
        )
        d.dict[lemma.word] = lemma
        d.accentless_words[lemma.get_word_no_accent()].add(lemma.word)

        alerted_usage.clean_alerted_words(d)
        self.assertIn('locative singular of скасува́ння (skasuvánnja)', alerted_usage.alerted_definitions)
        self.assertEqual(alerted_usage.alerted_definitions['locative singular of скасува́ння (skasuvánnja)']['relations'], ['form_of'])

    def test_parse_kaikki_entry_includes_links_and_strips_form_of_annotations(self):
        import extract

        entry = {
            'word': 'ску́чать',
            'pos': 'verb',
            'senses': [{
                'links': [['ску́чити', 'скучити#Ukrainian']],
                'glosses': ['third-person plural future indicative of ску́чити pf (skúčyty)'],
                'tags': ['form-of', 'future', 'indicative', 'plural', 'third-person'],
                'form_of': [{'word': 'ску́чити pf', 'extra': 'skúčyty'}]
            }]
        }

        parsed = extract._parse_kaikki_entry(entry)
        self.assertEqual(parsed['definitions'][0]['metadata']['relations'], ['form_of'])
        self.assertEqual(parsed['definitions'][0]['metadata']['targets'], ['ску́чити', 'ску́чити pf'])

    def test_find_word_candidates_cleans_form_of_target_when_needed(self):
        import dictionary

        d = dictionary.Dictionary(
            kaikki_path=os.environ['KAIKKI_PATH'],
            frequency_csv_path=os.environ['FREQUENCY_CSV_PATH']
        )
        base = dictionary.Word('ску́чити')
        d.dict[base.word] = base
        d.accentless_words[base.get_word_no_accent()].add(base.word)

        self.assertEqual(d._find_word_candidates('ску́чити pf'), ['ску́чити'])

    def test_clean_alerted_words_preserves_alt_of_metadata(self):
        import dictionary

        alerted_usage = dictionary.Usage('Петро', 'noun')
        alerted_metadata = {
            'relations': ['alt_of', 'abbreviation'],
            'targets': ['Петро'],
            'tags': ['alt-of', 'abbreviation']
        }
        alerted_usage.add_definition('abbreviation of Петро', alert=alerted_metadata)

        d = dictionary.Dictionary(
            kaikki_path=os.environ['KAIKKI_PATH'],
            frequency_csv_path=os.environ['FREQUENCY_CSV_PATH']
        )

        alerted_usage.clean_alerted_words(d)
        self.assertIn('abbreviation of Петро', alerted_usage.alerted_definitions)
        self.assertNotIn('relation', alerted_usage.alerted_definitions['abbreviation of Петро'])
        self.assertEqual(sorted(alerted_usage.alerted_definitions['abbreviation of Петро']['relations']), ['abbreviation', 'alt_of'])

    def test_parse_kaikki_entry_variant_relation_metadata(self):
        import extract

        jsonl_path = os.path.join(FIXTURES_DIR, 'kaikki_variant_relation.jsonl')
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            entry = json.loads(f.readline())

        parsed = extract._parse_kaikki_entry(entry)
        self.assertTrue(parsed['definitions'][0]['alert'])
        self.assertEqual(parsed['definitions'][0]['metadata']['relations'], ['diminutive'])
        self.assertIn('diminutive', parsed['definitions'][0]['metadata']['tags'])
        self.assertNotIn('relation', parsed['definitions'][0]['metadata'])

if __name__ == '__main__':
    unittest.main()
