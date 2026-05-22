import bz2
import os
import json
import multiprocessing
from collections import defaultdict
from copy import deepcopy

from dictionary import Word, cyrillic

# Resolve paths relative to this module, not CWD
_ETL_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.environ.get('DATA_DIR', 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# Caches are deprecated in offline mode
wiktionary_cache = {}
inflection_cache = {}

# Dummy viewstate values to avoid live connection on import
vs, vsg, ev = None, None, None

def get_viewstate(bs=None):
	return None, None, None

def get_ontolex(use_cache=True):
	raw_dbnary_path = os.environ.get('RAW_DBNARY_PATH', os.path.join(DATA_DIR, 'raw_dbnary_dump.ttl'))
	if use_cache and os.path.exists(raw_dbnary_path):
		return
	# Offline fallback
	if not os.path.exists(raw_dbnary_path):
		print(f"Warning: raw_dbnary_dump.ttl not found at {raw_dbnary_path}.")


# Lazy-loaded offline database
_wiktionary_database = None

def _ensure_wiktionary_loaded():
	global _wiktionary_database
	if _wiktionary_database is None:
		_wiktionary_database = load_wiktionary_jsonl()

def get_lemmas():
	_ensure_wiktionary_loaded()
	return list(set(w.word for w in _wiktionary_database))

def get_wiktionary_word(word, use_cache=True):
	_ensure_wiktionary_loaded()
	results = []
	for w in _wiktionary_database:
		if w.word == word or w.get_word_no_accent() == word.replace("́", ""):
			results.append(w)
	return results

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


def parse_wiktionary_table(w, inflections):
	# Kept for backward compatibility, but unused in offline jsonl mode
	return {}, None


def dump_wiktionary_cache():
	pass


def scrape_inflection(word):
	return [[None, None, None, None]]
			

def get_inflection(word, use_cache=True):
	# Complete offline lookup returning identical schema as live scraper
	word_spelling = word.word
	results = []
	
	_ensure_wiktionary_loaded()
	for w in _wiktionary_database:
		if w.word == word_spelling or w.get_word_no_accent() == word_spelling.replace("́", ""):
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

	no_accent = word_spelling.replace("́", "")

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
				word_info = ' '.join([Word.replace_pos(translations.get(x, x)) for x in word_info.split() if x in translations])
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


def get_frequency_list():
	FREQUENCY_CSV_PATH = os.environ.get('FREQUENCY_CSV_PATH', os.path.join(_ETL_DIR, 'sources', 'publicist_84k_lex_dict_orig.csv'))
	
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
	if not os.path.exists(FREQUENCY_CSV_PATH):
		print(f"Warning: frequency CSV not found at {FREQUENCY_CSV_PATH}")
		return data
		
	with open(FREQUENCY_CSV_PATH, 'r', encoding='utf-8') as f:
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
	
	# Locate canonical accented form if present
	for f in forms:
		if 'tags' in f and 'canonical' in f['tags']:
			word_spelling = f.get('form')
			break
			
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
		'intj': 'particle'
	}
	raw_pos = entry.get('pos', 'particle')
	pos = pos_map.get(raw_pos, raw_pos)
	
	definitions = []
	for sense in entry.get('senses', []):
		glosses = sense.get('glosses', [])
		for g in glosses:
			definitions.append(g)
			
	if not definitions:
		return None
		
	word_info_tags = []
	for f in forms:
		if 'tags' in f and 'canonical' in f['tags']:
			word_info_tags = [t for t in f['tags'] if t != 'canonical']
			break
	
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
			if f.get('source') in ('declension', 'conjugation') and 'tags' in f:
				tags = f['tags']
				form_val = f.get('form')
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
					gender = None
					if 'plural' in tags:
						gender = 'ap'
					elif 'masculine' in tags:
						gender = 'am'
					elif 'feminine' in tags:
						gender = 'af'
					elif 'neuter' in tags:
						gender = 'an'
						
					if case and gender:
						key = f"{case} {gender}"
						forms_dict[key].append(form_val)
						
					if 'comparative' in tags:
						forms_dict['addl comp'].append(form_val)
					elif 'superlative' in tags:
						forms_dict['addl super'].append(form_val)
					elif 'adverb' in tags:
						forms_dict['addl adv'].append(form_val)
						
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

	return {
		'word': word_spelling,
		'pos': pos,
		'definitions': definitions,
		'forms': dict(forms_dict) if forms_dict else None,
		'form_type': form_type,
		'info': word_info
	}


def _parse_chunk_worker(lines_chunk):
	results = []
	for line in lines_chunk:
		if not line.strip():
			continue
		try:
			entry = json.loads(line)
			if entry.get('lang') == 'Ukrainian':
				word_data = _parse_kaikki_entry(entry)
				if word_data:
					results.append(word_data)
		except Exception:
			pass
	return results


def load_wiktionary_jsonl():
	kaikki_path = os.environ.get('KAIKKI_PATH', os.path.join(_ETL_DIR, 'sources', 'kaikki.org-dictionary-Ukrainian.jsonl'))
	if not os.path.exists(kaikki_path):
		print(f"Error: {kaikki_path} not found.")
		return []
		
	print(f"loading wiktionary jsonl from {kaikki_path} (multi-process)")
	
	with open(kaikki_path, 'r', encoding='utf-8') as f:
		lines = f.readlines()
		
	num_lines = len(lines)
	print(f"Total lines to parse: {num_lines}")
	
	chunk_size = 5000
	chunks = [lines[i:i + chunk_size] for i in range(0, num_lines, chunk_size)]
	
	num_cores = max(1, multiprocessing.cpu_count() - 1)
	print(f"Using {num_cores} worker processes")
	
	parsed_entries = []
	with multiprocessing.Pool(processes=num_cores) as pool:
		chunk_results = pool.map(_parse_chunk_worker, chunks)
		for res in chunk_results:
			parsed_entries.extend(res)
			
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
			w.add_definition(pos, d)
			
		if pe['info']:
			w.add_info(Word.replace_pos(pos), pe['info'])
			
		if pe['forms']:
			w.add_forms(Word.replace_pos(pos), pe['forms'], pe['form_type'])
			
	print(f"Extracted {len(words_map)} unique words.")
	return list(words_map.values())