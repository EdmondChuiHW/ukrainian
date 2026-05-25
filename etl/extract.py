import bz2
import os
import re
import json
import multiprocessing
from collections import defaultdict
from copy import deepcopy

from dictionary import Word, cyrillic

# Prefer a faster JSON parser when available, with a safe json fallback.
try:
    import orjson as _fast_json
except ImportError:
    try:
        import ujson as _fast_json
    except ImportError:
        _fast_json = json

JSON_PARSER = _fast_json.__name__

def _json_loads(line):
    return _fast_json.loads(line)

# Resolve paths relative to this module, not CWD
_ETL_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.environ.get('DATA_DIR', 'cache')
os.makedirs(DATA_DIR, exist_ok=True)

# Caches are deprecated in offline mode
wiktionary_cache = {}
inflection_cache = {}

def get_ontolex(raw_dbnary_path, use_cache=True):
	if use_cache and os.path.exists(raw_dbnary_path):
		return
	if not os.path.exists(raw_dbnary_path):
		raise FileNotFoundError(f"{raw_dbnary_path} not found")


# Lazy-loaded offline database
_wiktionary_database = None
_wiktionary_index = None

def _build_wiktionary_index(words):
	index = {
		'exact': defaultdict(list),
		'accentless': defaultdict(list),
	}
	for w in words:
		index['exact'][w.word].append(w)
		index['accentless'][w.get_word_no_accent()].append(w)
	return index


def _ensure_wiktionary_loaded(kaikki_path):
	global _wiktionary_database, _wiktionary_index
	if _wiktionary_database is None:
		_wiktionary_database = load_wiktionary_jsonl(kaikki_path)
		_wiktionary_index = _build_wiktionary_index(_wiktionary_database)


def get_additional_adjectival_forms(text):
	# Corrected adjectival prefix extraction logic
	def get_word(word):
		prefix = ''
		rest = ''
		parenthesis = 0
		for i in word:
			if i == '(':
				parenthesis += 1
			elif i == ')':
				parenthesis -= 1
			elif parenthesis > 0:
				prefix += i
			else:
				rest += i
		return [rest] if len(prefix) == 0 else [rest, prefix + rest]
				
	last_parenthesis = ''
	parenthesis = 0
	for i in text[::-1]:
		if i == '(':
			parenthesis -= 1
		if parenthesis > 0:
			last_parenthesis = i + last_parenthesis
		if i == ')':
			parenthesis += 1
		if parenthesis == 0 and len(last_parenthesis) > 0:
			break
	lists = [x.split() for x in last_parenthesis.split(',')]
	results = {}
	abbrevs = {
		'comparative': 'addl comp',
		'superlative': 'addl super',
		'argumentative': 'addl arg',
		'adverb': 'addl adv'
	}
	for form in lists:
		if form and form[0] in abbrevs.keys():
			if len(form) == 2:
				results[abbrevs[form[0]]] = get_word(form[1])
			elif len(form) == 4:
				results[abbrevs[form[0]]] = get_word(form[1]) + get_word(form[3])
	return results

def get_inflection(word, kaikki_path, use_cache=True):
	# Complete offline lookup returning identical schema as live scraper
	word_spelling = word.word
	results = []
	
	_ensure_wiktionary_loaded(kaikki_path)
	word_base = word.get_word_no_accent()
	lookup_words = []
	if _wiktionary_index is not None:
		lookup_words.extend(_wiktionary_index['exact'].get(word_spelling, []))
		lookup_words.extend(_wiktionary_index['accentless'].get(word_base, []))	
	else:
		lookup_words = list(_wiktionary_database)

	seen = set()
	for w in lookup_words:
		if w.word in seen:
			continue
		seen.add(w.word)
		if w.word == word_spelling or w.get_word_no_accent() == word_base:
			for pos, usage in w.usages.items():
				forms = usage.get_forms()
				form_type = None
				for ft in usage.forms:
					form_type = ft
				results.append([w.word, usage.get_info(), forms, form_type])
	
	if not results:
		return [[None, None, None, None]]
	
	# Strict input check and translation mapping
	translations = {
		'або': 'or',
		'абревіатура': 'abbreviations',
		'вигук': 'interjection',
		'виду': 'form',
		'вищий': 'highest',
		'власна': 'own',
		'вставне': 'interjection',
		'два': 'two',
		'доконаного': 'perfective',
		'дієприкметник': 'adjective',
		'дієприслівник': 'adverb',
		'дієслово': 'verb',
		'жіночого': 'female',
		'з': 'with',
		'займенник': 'pronoun',
		'кількісний': 'determiner',
		'множинний': 'plural',
		'назва': 'noun',
		'найвищий': 'lowest',
		'недоконаного': 'imperfective',
		'порядковий': 'adjective',
		'прийменник': 'preposition',
		'прийменником': 'preposition',
		'прикметник': 'adjective',
		'прислівник': 'adverb',
		'прислівником': 'adverb',
		'присудкове': 'predicate',
		'прізвище': 'noun',
		'роду': 'gender',
		'середнього': 'neuter',
		'слово': 'word',
		'сполука': 'conjunction',
		'сполучник': 'conjunction',
		'ступінь': 'degree',
		'типу': 'type',
		'частка': 'particle',
		'часткою': 'particle',
		'числівник': 'numeral',
		'чоловічого': 'male',
		'і': 'and',
		'іменник': 'noun',
		'істота': 'animate',
	}

	no_accent = word_base

	def clean_result(res):
		if not res or len(res) < 4:
			return (None, None, None, None)
		found_word, word_info, forms, form_type = res
		if found_word:
			word_len = len(no_accent.split())
			found_word = ' '.join(found_word.split()[:word_len])
			forms = deepcopy(forms) if forms is not None else {}
			
			if word_info:
				word_info = ''.join([x for x in word_info if x in cyrillic + "' "])
				word_info = ' '.join([Word.normalize_pos(translations.get(x, x)) for x in word_info.split() if x in translations])
			else:
				word_info = ''
			
			for form_id in list(forms.keys()):
				form = forms[form_id]
				if form == "" or form is None:
					del forms[form_id]
			for form_id in forms:
				form = forms[form_id]
				if isinstance(form, str):
					forms[form_id] = [x.strip() for x in form.split(',')]
				else:
					forms[form_id] = [x.strip() for x in form]
				forms[form_id] = [' '.join(x.split()[-1 * word_len:]) for x in forms[form_id]]
			return (found_word, word_info, forms, form_type)
		return res

	return [clean_result(x) for x in results]


def dump_inflection_cache():
	pass


def get_frequency_list(frequency_csv_path):
	if not os.path.exists(frequency_csv_path):
		raise FileNotFoundError(f"{frequency_csv_path} not found")
	
	parts_of_speech = {
		'': None, 
		'абревіатура': 'abbreviation', 
		'вигук': 'interjection', 
		'дієсл.': 'verb', 
		'займ.': 'pronoun',
		'займ.-прикм.': 'pronoun',
		'займ.-ім.': 'pronoun',
		'прийм.': 'preposition', 
		'прикметник': 'adjective', 
		'прислівн.': 'adverb', 
		'присудкова форма': 'predicate', 
		'сполучн.': 'conjugation', 
		'форма на -но/-то': None,
		'част.': 'particle', 
		'числ.': 'numeral', 
		'ім. ж. р.': 'noun',
		'ім. множ.': 'noun',
		'ім. с. р.': 'noun',
		'ім. ч. р.': 'noun',
		'скорочення': 'abbreviation',
		'дієприсл.': 'participle'
	}
	data = defaultdict(lambda: {})
	with open(frequency_csv_path, 'r', encoding='utf-8') as f:
		lines = f.read().split('\n')
		if len(lines) > 0:
			for line in lines[1:]:
				if not line.strip():
					continue
				parts = line.split(';')
				if len(parts) >= 3:
					rank = parts[0].strip()
					word = parts[1].strip()
					pos_ukr = parts[2].strip()
					
					mapped_pos = parts_of_speech.get(pos_ukr, None)
					try:
						data[word][mapped_pos] = int(rank)
					except ValueError:
						pass
	return data


# --- Multi-process Kaikki JSONL Loader ---

def _parse_kaikki_entry(entry):
	word_spelling = entry.get('word')
	forms = entry.get('forms', [])
	
	def _strip_stress(text):
		return text.replace('́', '') if text else text

	def _parse_relation_metadata(source):
		tags = source.get('tags') or []
		relations = []
		targets = []
		if isinstance(source.get('form_of'), list) and source['form_of']:
			relations.append('form_of')
		targets.extend([
			item.get('word').strip()
			for item in source.get('form_of', [])
			if isinstance(item, dict) and isinstance(item.get('word'), str)
		])
		if any(t in ('form-of', 'form_of') for t in tags):
			relations.append('form_of')
		if isinstance(source.get('alt_of'), list) and source['alt_of']:
			relations.append('alt_of')
		targets.extend([
			item.get('word').strip()
			for item in source.get('alt_of', [])
			if isinstance(item, dict) and isinstance(item.get('word'), str)
		])
		if isinstance(source.get('alt-of'), list) and source['alt-of']:
			relations.append('alt_of')
		targets.extend([
			item.get('word').strip()
			for item in source.get('alt-of', [])
			if isinstance(item, dict) and isinstance(item.get('word'), str)
		])
		if 'form_of' in relations and isinstance(source.get('links'), list):
			for link in source.get('links'):
				if isinstance(link, (list, tuple)) and link:
					link_target = link[0]
				elif isinstance(link, str):
					link_target = link
				else:
					link_target = None
				if link_target:
					targets.append(link_target.strip())
		relation_tags = [t for t in tags if t in ('alternative', 'abbreviation', 'diminutive', 'augmentative', 'comparative', 'dialectal', 'variant', 'contraction')]
		relations.extend(relation_tags)
		if relations:
			priority = ['form_of', 'alt_of', 'abbreviation', 'alternative', 'diminutive', 'augmentative', 'comparative', 'variant', 'contraction']
			unique_relations = [rel for rel in priority if rel in relations]
			for rel in relations:
				if rel not in unique_relations:
					unique_relations.append(rel)
			chosen_relation = unique_relations[0]
			metadata = {
				'relations': unique_relations,
				'targets': sorted({target for target in targets if target}),
				'tags': sorted(set(tags)),
			}
			return metadata
		return None

	pos_map = {
		'noun': 'noun',
		'verb': 'verb',
		'adj': 'adjective',
		'adv': 'adverb',
		'pron': 'pronoun',
		'prep': 'preposition',
		'conj': 'particle',
		'part': 'particle',
		'num': 'numeral',
		'intj': 'particle',
		'name': 'noun',
		'proper noun': 'noun'
	}
	raw_pos = entry.get('pos', 'particle')
	pos = pos_map.get(raw_pos, raw_pos)

	# Preserve the original raw word plus canonical and alternate lexical variants.
	parsed_spellings = [(word_spelling, pos)]
	parsed_keys = {(word_spelling, pos)}

	for f in forms:
		if f.get('source') in ('declension', 'conjugation'):
			continue
		candidate = f.get('form')
		tags = f.get('tags') or []
		if not candidate or candidate == '-' or 'romanization' in tags:
			continue
		if any(tag in tags for tag in ('canonical', 'alternative', 'initialism', 'abbreviation', 'variant', 'diminutive', 'augmentative', 'contraction')):
			if any(ch in cyrillic for ch in candidate):
				if (candidate, pos) not in parsed_keys:
					parsed_spellings.append((candidate, pos))
					parsed_keys.add((candidate, pos))
				if any(tag in tags for tag in ('initialism', 'abbreviation')) and pos != 'particle':
					if (candidate, 'particle') not in parsed_keys:
						parsed_spellings.append((candidate, 'particle'))
						parsed_keys.add((candidate, 'particle'))

	# Collapse accent-only canonical variants into a single representative entry,
	# preserving alternate stress patterns as neutral variant metadata.
	grouped_spellings = defaultdict(list)
	for candidate, candidate_pos in parsed_spellings:
		grouped_spellings[(candidate.replace('́', ''), candidate_pos)].append(candidate)

	collapsed_spellings = []
	for (base, candidate_pos), spellings in grouped_spellings.items():
		unique_spellings = []
		for candidate in spellings:
			if candidate not in unique_spellings:
				unique_spellings.append(candidate)

		# If the raw lemma is accentless but there are accented canonical forms for
		# the same base, drop the raw accentless lemma from the group.
		if word_spelling.replace('́', '') == word_spelling:
			accented_candidates = [x for x in unique_spellings if x.replace('́', '') != x]
			if accented_candidates and word_spelling in unique_spellings:
				unique_spellings = [x for x in unique_spellings if x != word_spelling]

		if len(unique_spellings) > 1:
			if word_spelling in unique_spellings:
				primary = word_spelling
			else:
				accented_candidates = [x for x in unique_spellings if x.replace('́', '') != x]
				primary = accented_candidates[0] if accented_candidates else unique_spellings[0]
			variants = [x for x in unique_spellings if x != primary]
			collapsed_spellings.append((primary, candidate_pos, variants))
		else:
			collapsed_spellings.append((unique_spellings[0], candidate_pos, []))

	parsed_spellings = collapsed_spellings
	definitions = []
	entry_metadata = _parse_relation_metadata(entry)
	def _merge_relation_metadata(base, override):
		if not base:
			return override
		if not override:
			return base
		relations = sorted(set(base.get('relations', []) + override.get('relations', [])))
		targets = sorted(set(base.get('targets', []) + override.get('targets', [])))
		tags = sorted(set(base.get('tags', []) + override.get('tags', [])))
		return {
			'relations': relations,
			'targets': targets,
			'tags': tags,
		}

	for sense in entry.get('senses', []):
		glosses = sense.get('glosses', [])
		sense_metadata = _parse_relation_metadata(sense)
		combined_metadata = _merge_relation_metadata(entry_metadata, sense_metadata)
		for g in glosses:
			alert = bool(combined_metadata)
			definitions.append({'definition': g, 'alert': alert, 'metadata': combined_metadata})
	
	word_info_tags = []
	def add_word_info_tags(tags):
		for tag in tags or []:
			if tag == 'canonical':
				continue
			if tag not in word_info_tags:
				word_info_tags.append(tag)

	for f in forms:
		if 'tags' in f and 'canonical' in f['tags']:
			add_word_info_tags(f['tags'])
			break
	if entry_metadata:
		add_word_info_tags(entry_metadata.get('tags'))
	for sense in entry.get('senses', []):
		add_word_info_tags(sense.get('tags'))
	word_info = ' '.join(word_info_tags) if word_info_tags else ''
	
	form_type = None
	if pos == 'noun':
		form_type = 'noun'
	elif pos == 'verb':
		form_type = 'verb'
	elif pos == 'adjective':
		form_type = 'adj'
		
	forms_dict = defaultdict(list)
	
	if form_type:
		for f in forms:
			tags = f.get('tags') or []
			form_val = f.get('form')
			if not form_val or form_val == '-':
				continue

			source = f.get('source')
			if source in ('declension', 'conjugation') and 'tags' in f:
				tags = f['tags']
				if not form_val or form_val == '-':
					continue

				if form_type == 'noun':
					cases = {'nominative': 'nom', 'genitive': 'gen', 'dative': 'dat', 'accusative': 'acc', 'instrumental': 'ins', 'locative': 'loc', 'vocative': 'voc'}
					case = None
					for c_tag, c_val in cases.items():
						if c_tag in tags:
							case = c_val
							break
					num = None
					if 'singular' in tags:
						num = 's'
					elif 'plural' in tags:
						num = 'p'

					if case and num:
						key = f"{case} n{num}"
						forms_dict[key].append(form_val)

				elif form_type == 'adj':
					cases = {'nominative': 'nom', 'genitive': 'gen', 'dative': 'dat', 'accusative': 'acc', 'instrumental': 'ins', 'locative': 'loc', 'vocative': 'voc'}
					case = None
					for c_tag, c_val in cases.items():
						if c_tag in tags:
							case = c_val
							break
					genders = []
					if 'plural' in tags:
						genders.append('ap')
					else:
						if 'masculine' in tags:
							genders.append('am')
						if 'feminine' in tags:
							genders.append('af')
						if 'neuter' in tags:
							genders.append('an')

					if case and genders:
						for gender in genders:
							key = f"{case} {gender}"
							forms_dict[key].append(form_val)

				elif form_type == 'verb':
					if 'infinitive' in tags:
						forms_dict['inf'].append(form_val)
					elif 'present' in tags:
						person = None
						if 'first-person' in tags: person = '1'
						elif 'second-person' in tags: person = '2'
						elif 'third-person' in tags: person = '3'
						num = None
						if 'singular' in tags: num = 's'
						elif 'plural' in tags: num = 'p'
						if person and num:
							forms_dict[f"pres {person}{num}"].append(form_val)
					elif 'future' in tags:
						person = None
						if 'first-person' in tags: person = '1'
						elif 'second-person' in tags: person = '2'
						elif 'third-person' in tags: person = '3'
						num = None
						if 'singular' in tags: num = 's'
						elif 'plural' in tags: num = 'p'
						if person and num:
							forms_dict[f"fut {person}{num}"].append(form_val)
					elif 'imperative' in tags:
						person = None
						if 'first-person' in tags: person = '1'
						elif 'second-person' in tags: person = '2'
						elif 'third-person' in tags: person = '3'
						num = None
						if 'singular' in tags: num = 's'
						elif 'plural' in tags: num = 'p'
						if person and num:
							forms_dict[f"imp {person}{num}"].append(form_val)
					elif 'past' in tags:
						if 'plural' in tags:
							forms_dict['past p'].append(form_val)
						elif 'masculine' in tags:
							forms_dict['past ms'].append(form_val)
						elif 'feminine' in tags:
							forms_dict['past fs'].append(form_val)
						elif 'neuter' in tags:
							forms_dict['past ns'].append(form_val)

					if 'adverbial' in tags:
						if 'present' in tags:
							forms_dict['pres adv pp'].append(form_val)
						elif 'past' in tags:
							forms_dict['past adv pp'].append(form_val)
					elif 'active' in tags:
						if 'present' in tags:
							forms_dict['pres act pp'].append(form_val)
						elif 'past' in tags:
							forms_dict['past act pp'].append(form_val)
					elif 'passive' in tags:
						if 'present' in tags:
							forms_dict['pres pas pp'].append(form_val)
						elif 'past' in tags:
							forms_dict['past pas pp'].append(form_val)
			elif form_type == 'adj' and any(tag in tags for tag in ('comparative', 'superlative', 'argumentative', 'adverb')):
				if 'comparative' in tags:
					forms_dict['addl comp'].append(form_val)
				if 'superlative' in tags:
					forms_dict['addl super'].append(form_val)
				if 'argumentative' in tags:
					forms_dict['addl arg'].append(form_val)
				if 'adverb' in tags:
					forms_dict['addl adv'].append(form_val)
	parsed_entries = []
	for ws, ws_pos, variants in parsed_spellings:
		parsed_entries.append({
			'word': ws,
			'pos': ws_pos,
			'variants': variants or None,
			'definitions': definitions,
			'forms': dict(forms_dict) if forms_dict else None,
			'form_type': form_type,
			'info': word_info
		})

	for relation_source in ('related', 'derived'):
		for item in entry.get(relation_source, []):
			candidate = item.get('word')
			if not candidate or not isinstance(candidate, str):
				continue
			if any(ch in cyrillic for ch in candidate):
				candidate_pos = pos
				if candidate.startswith('-'):
					candidate_pos = 'combining form'
				if (candidate, candidate_pos) not in parsed_keys:
					parsed_entries.append({
						'word': candidate,
						'pos': candidate_pos,
						'definitions': definitions,
						'forms': None,
						'form_type': None,
						'info': word_info
					})
					parsed_keys.add((candidate, candidate_pos))

	return parsed_entries if len(parsed_entries) > 1 else parsed_entries[0]


def _parse_chunk_worker(lines_chunk):
	results = []
	for line in lines_chunk:
		if not line.strip():
			continue
		try:
			entry = _json_loads(line)
			if entry.get('lang') == 'Ukrainian':
				word_data = _parse_kaikki_entry(entry)
				if word_data:
					if isinstance(word_data, list):
						results.extend(word_data)
					else:
						results.append(word_data)
		except Exception:
			pass
	return results


def _iter_jsonl_chunks(file_path, chunk_size=5000):
	with open(file_path, 'r', encoding='utf-8') as f:
		chunk = []
		for line in f:
			chunk.append(line)
			if len(chunk) >= chunk_size:
				yield chunk
				chunk = []
		if chunk:
			yield chunk


def load_wiktionary_jsonl(kaikki_path):
	if not os.path.exists(kaikki_path):
		raise FileNotFoundError(f"{kaikki_path} not found")

	chunk_size = 5000
	num_cores = max(1, multiprocessing.cpu_count() - 1)
	print(f"Using {JSON_PARSER} parser and {num_cores} worker processes")

	parsed_entries = []
	with multiprocessing.Pool(processes=num_cores) as pool:
		for res in pool.imap(_parse_chunk_worker, _iter_jsonl_chunks(kaikki_path, chunk_size), chunksize=1):
			if isinstance(res, list):
				parsed_entries.extend(res)
			elif res:
				parsed_entries.append(res)
	print(f"Merging {len(parsed_entries)} entries in main process...")
	words_map = {}
	for pe in parsed_entries:
		word_spelling = pe['word']
		pos = pe['pos']
		if not word_spelling:
			continue

		if word_spelling not in words_map:
			words_map[word_spelling] = Word(word_spelling)
		
		w = words_map[word_spelling]

		for d in pe['definitions']:
			if isinstance(d, dict):
				alert_value = d.get('metadata') if d.get('alert') else False
				w.add_definition(pos, d['definition'], alert=alert_value)
			else:
				w.add_definition(pos, d)

		if pe.get('variants'):
			w.add_variants(pe['variants'])
		if pe.get('info'):
			w.add_info(pos, pe['info'])
		if pe.get('forms') and pe.get('form_type'):
			w.add_forms(pos, pe['forms'], pe['form_type'])
	return list(words_map.values())
