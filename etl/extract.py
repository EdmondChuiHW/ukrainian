import os
import re
import json
import multiprocessing
from collections import defaultdict
from copy import deepcopy
from functools import lru_cache
from typing import Optional

from dictionary import Word, cyrillic
from helpers import strip_stress

# Prefer a faster JSON parser when available, with a safe json fallback.
try:
    import orjson as _fast_json
except ImportError:
    try:
        import ujson as _fast_json
    except ImportError:
        _fast_json = json

JSON_PARSER = _fast_json.__name__

_GENDER_MAP = {
	'feminine': 'female',
	'masculine': 'male',
	'neuter': 'neuter',
}

_ANIMACY_TAGS = {
	'animate': 'animate',
	'inanimate': 'inanimate',
	'person': 'animate',
	'animal': 'animate',
}

_ASPECT_TAGS = {
	'imperfective': 'imperfective',
	'perfective': 'perfective',
}

CANDIDATE_RE = re.compile(r"(?:[А-Яа-яЁёЇїІіЄєҐґ](?:[\u0300-\u036f]*))+", re.UNICODE)
DIACRITIC_RE = re.compile(r"[\u0300-\u036f]")

# Structured grammar tags that should be excluded from prefix
# (they're already captured in the grammar field)
_STRUCTURED_TAGS = {
	# Gender
	'feminine', 'masculine', 'neuter',
	# Animacy
	'animate', 'inanimate', 'person', 'animal',
	# Aspect
	'imperfective', 'perfective',
	# Number
	'singular', 'plural',
	# Case
	#'nominative', 'genitive', 'dative', 'accusative', 'instrumental', 'locative', 'vocative',
	# Tense
	'present', 'past', 'future', 'imperative', 'infinitive',
	# Voice/Mood
	#'active', 'passive', 'reflexive', 'conditional',
	# Person
	#'first-person', 'second-person', 'third-person',
	# Other structural
	#'inclusive', 'exclusive', 'formal', 'informal',
}

def _json_loads(line):
    return _fast_json.loads(line)


def _build_grammar_info(tags):
	"""Build structured grammar info from deterministic source tags."""
	info = {
		'gender': None,
		'animacy': None,
		'aspect': None,
	}
	for tag in tags or []:
		if tag in _GENDER_MAP and info['gender'] is None:
			info['gender'] = _GENDER_MAP[tag]
		if tag in _ANIMACY_TAGS and info['animacy'] is None:
			info['animacy'] = _ANIMACY_TAGS[tag]
		if tag in _ASPECT_TAGS and info['aspect'] is None:
			info['aspect'] = _ASPECT_TAGS[tag]
	return info


def _normalize_word(word: str) -> str:
	return strip_stress(word)


def _extract_candidates(raw_value: Optional[str]) -> list:
	if not raw_value:
		return []
	value = str(raw_value)
	value = re.sub(r"<[^>]+>", "", value)
	value = value.replace(" or ", ",")
	candidates = []
	for chunk in re.split(r"[,/;|]+", value):
		for match in CANDIDATE_RE.findall(chunk):
			candidate = _normalize_word(match)
			if candidate and candidate not in candidates:
				candidates.append(candidate)
	return candidates


def _extract_synonyms(raw_synonyms) -> list:
	synonyms = []
	if not raw_synonyms:
		return synonyms
	for item in raw_synonyms:
		word = ''
		if isinstance(item, str):
			word = item.strip()
		elif isinstance(item, dict):
			word = item.get('word') or item.get('alt') or item.get('roman') or ''
		else:
			continue
		word = str(word).strip()
		if not word:
			continue
		if not CANDIDATE_RE.search(word):
			continue
		if word not in synonyms:
			synonyms.append(word)
	return synonyms


def _opposite_aspect(aspect: Optional[str]) -> Optional[str]:
	if aspect == 'perfective':
		return 'imperfective'
	if aspect == 'imperfective':
		return 'perfective'
	return None


def _extract_verb_aspect_candidates(entry: dict, source_aspect: Optional[str] = None) -> list:
	if entry.get('pos') != 'verb':
		return []
	source_word = entry.get('word')
	if not source_word:
		return []
	target_aspect = _opposite_aspect(source_aspect)
	canonical_source = _normalize_word(source_word)
	candidates = []

	def add_candidate(value):
		if not value or not isinstance(value, str):
			return
		candidate = _normalize_word(value)
		if candidate and candidate != canonical_source and candidate not in candidates:
			candidates.append(candidate)

	for form in entry.get('forms', []):
		tags = [str(t).lower() for t in form.get('tags') or [] if t]
		if not any(t in ('perfective', 'imperfective') for t in tags):
			continue
		if target_aspect and target_aspect not in tags:
			continue
		add_candidate(form.get('form'))

	if candidates:
		return candidates

	for form in entry.get('forms', []):
		tags = [str(t).lower() for t in form.get('tags') or [] if t]
		if not any(t in ('perfective', 'imperfective') for t in tags):
			continue
		if target_aspect and target_aspect not in tags:
			continue
		for link in form.get('links', []):
			if isinstance(link, (list, tuple)) and link:
				add_candidate(link[0])
			elif isinstance(link, str):
				add_candidate(link)

	if candidates:
		return candidates

	for head_template in entry.get('head_templates', []):
		args = head_template.get('args', {})
		for key in ('impf', 'pf'):
			if target_aspect and ((key == 'impf' and target_aspect != 'imperfective') or (key == 'pf' and target_aspect != 'perfective')):
				continue
			for candidate in _extract_candidates(args.get(key)):
				add_candidate(candidate)

	return candidates

# Resolve paths relative to this module, not CWD
_ETL_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.environ.get('DATA_DIR', 'cache')
os.makedirs(DATA_DIR, exist_ok=True)

# Caches are deprecated in offline mode
wiktionary_cache = {}
inflection_cache = {}

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
				results.append([w.word, usage.get_grammar_info(), forms, form_type])
	
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
			
			if isinstance(word_info, dict):
				word_info = deepcopy(word_info)
			elif word_info:
				word_info = ''.join([x for x in word_info if x in cyrillic + "' "])
				word_info = ' '.join([Word.normalize_pos(translations.get(x, x)) for x in word_info.split() if x in translations])
			else:
				word_info = {}
			
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
		'proper noun': 'noun',
		'det': 'particle'
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
		grouped_spellings[(strip_stress(candidate), candidate_pos)].append(candidate)

	collapsed_spellings = []
	for (base, candidate_pos), spellings in grouped_spellings.items():
		unique_spellings = []
		for candidate in spellings:
			if candidate not in unique_spellings:
				unique_spellings.append(candidate)

		# If the raw lemma is accentless but there are accented canonical forms for
		# the same base, drop the raw accentless lemma from the group.
		if strip_stress(word_spelling) == word_spelling:
			accented_candidates = [x for x in unique_spellings if strip_stress(x) != x]
			if accented_candidates and word_spelling in unique_spellings:
				unique_spellings = [x for x in unique_spellings if x != word_spelling]

		if len(unique_spellings) > 1:
			if word_spelling in unique_spellings:
				primary = word_spelling
			else:
				accented_candidates = [x for x in unique_spellings if strip_stress(x) != x]
				primary = accented_candidates[0] if accented_candidates else unique_spellings[0]
			variants = [x for x in unique_spellings if x != primary]
			collapsed_spellings.append((primary, candidate_pos, variants))
		else:
			collapsed_spellings.append((unique_spellings[0], candidate_pos, []))

	parsed_spellings = collapsed_spellings
	definitions = []
	entry_metadata = _parse_relation_metadata(entry)
	entry_synonyms = _extract_synonyms(entry.get('synonyms'))
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
		tags = sense.get('tags') or []
		qualifier = sense.get('qualifier')

		prefix_parts = []
		if qualifier:
			q_str = qualifier.strip()
			if 'case' in q_str.lower() and not q_str.startswith('+'):
				q_str = f"+{q_str}"
			prefix_parts.append(q_str)
		for tag in tags:
			if tag not in ('form-of', 'alt-of', 'canonical', 'table-tags', 'inflection-template') and tag not in _STRUCTURED_TAGS:
				prefix_parts.append(tag)
		prefix = prefix_parts if prefix_parts else None

		sense_metadata = _parse_relation_metadata(sense)
		combined_metadata = _merge_relation_metadata(entry_metadata, sense_metadata)
		for g in glosses:
			alert = bool(combined_metadata)
			sense_synonyms = _extract_synonyms(sense.get('synonyms'))
			definitions.append({
				'definition': g,
				'prefix': prefix,
				'alert': alert,
				'metadata': combined_metadata,
				'synonyms': sense_synonyms,
			})
	
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
      # Don't break on the first canonical tag.
      # There could be multiple, e.g. постаріти
      # First doesn't have the "perfective" tag, second does.
			# break

	if entry_metadata:
		add_word_info_tags(entry_metadata.get('tags'))
	for sense in entry.get('senses', []):
		add_word_info_tags(sense.get('tags'))
	word_info = _build_grammar_info(word_info_tags)
	aspect_candidates = _extract_verb_aspect_candidates(entry, word_info.get('aspect'))
	
	# Determine form_type based on inflection_templates
	inflection_templates = entry.get('inflection_templates') or []
	template_names = [t.get('name', '').lower() for t in inflection_templates if isinstance(t, dict)]
	
	form_type = None
	if any('conj' in name for name in template_names):
		form_type = 'verb'
	elif any('adecl' in name for name in template_names):
		form_type = 'adj'
	elif any('ndecl' in name for name in template_names):
		form_type = 'noun'
	
	if form_type is None:
		if pos == 'noun':
			form_type = 'noun'
		elif pos == 'verb':
			form_type = 'verb'
		elif pos == 'adjective':
			form_type = 'adj'
		elif pos == 'pronoun':
			form_type = 'pronoun'
		
	forms_dict = defaultdict(list)
	pronoun_form_persons = defaultdict(set)  # Track which persons belong to each form key
	
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

				elif form_type == 'pronoun':
					# Strip parenthetical romanization for pronoun forms
					# e.g. 'ньо́го (johó, nʹóho*)' -> 'ньо́го'
					form_val = re.sub(r'\s*\([^)]*[a-zA-Z][^)]*\)\*?', '', form_val).rstrip('*').strip()
					if not form_val or form_val == '-':
						continue
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

					# Track person and gender for pronoun forms
					person = None
					if 'first-person' in tags: person = '1'
					elif 'second-person' in tags: person = '2'
					elif 'third-person' in tags: person = '3'
					
					gender = None
					if 'masculine' in tags and num == 's': gender = 'm'
					elif 'feminine' in tags and num == 's': gender = 'f'
					elif 'neuter' in tags and num == 's': gender = 'n'
					
					if case and num:
						key = f"{case} n{num}"
						forms_dict[key].append(form_val)
						# Record person/gender marker for this form
						if person or gender:
							person_key = f"{person or 'x'}{gender or 'x'}{num}"
							pronoun_form_persons[key].add((form_val, person_key))
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
		entry_forms = dict(forms_dict) if forms_dict else None
		
		# For pronouns, filter forms to only include the specific word being processed
		if form_type == 'pronoun' and entry_forms and pronoun_form_persons:
			ws_no_accent = strip_stress(ws)
			# Find which person/gender this pronoun entry corresponds to
			target_person_keys = set()
			for form_key, form_person_pairs in pronoun_form_persons.items():
				for form_val, person_key in form_person_pairs:
					if strip_stress(form_val) == ws_no_accent:
						target_person_keys.add(person_key)
			
			# If we found person/gender markers for this word, filter accordingly
			if target_person_keys:
				filtered_forms = {}
				for form_key, form_values in entry_forms.items():
					filtered_values = [fv for fv, pk in pronoun_form_persons[form_key] if pk in target_person_keys]
					if filtered_values:
						filtered_forms[form_key] = filtered_values
				entry_forms = filtered_forms if filtered_forms else None

		parsed_entries.append({
			'word': ws,
			'pos': ws_pos,
			'variants': variants or None,
			'definitions': definitions,
			'synonyms': entry_synonyms or None,
			'forms': entry_forms,
			'form_type': form_type,
			'info': word_info,
			'aspect_candidates': aspect_candidates if aspect_candidates else None,
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
						'definitions': [],
						'forms': None,
						'form_type': None,
						'info': None,
						'aspect_candidates': None,
					})
					parsed_keys.add((candidate, candidate_pos))

	return parsed_entries if len(parsed_entries) > 1 else parsed_entries[0]


def _extract_translation_definition(entry, translation, sense=None):
	if not isinstance(translation, dict):
		return None
	if isinstance(sense, dict):
		for gloss_field in ('raw_glosses', 'glosses'):
			glosses = sense.get(gloss_field)
			if isinstance(glosses, list) and glosses:
				return str(glosses[0]).strip()
	definition = translation.get('sense')
	if isinstance(definition, str) and definition.strip():
		return definition.strip()
	return None


def _parse_english_translation_entry(entry):
	parsed_entries = []
	seen = set()

	def build_translation_entry(translation, sense_context=None):
		if not isinstance(translation, dict):
			return
		lang_code = str(translation.get('lang_code') or translation.get('code') or '').lower()
		lang = str(translation.get('lang') or '').lower()
		if lang_code != 'uk' and lang != 'ukrainian':
			return
		word = translation.get('word')
		if not word or not isinstance(word, str):
			return
		if not any(ch in cyrillic for ch in word):
			return
		definition = _extract_translation_definition(entry, translation, sense_context)
		if not definition:
			return
		pos = entry.get('pos', 'particle')
		key = (word.strip(), pos, definition)
		if key in seen:
			return
		seen.add(key)
		info = _build_grammar_info([t for t in (translation.get('tags') or []) if isinstance(t, str)])
		source_word = entry.get('word') if isinstance(entry.get('word'), str) else None
		parsed_entries.append({
			'word': word.strip(),
			'pos': pos,
			'variants': None,
			'definitions': [definition],
			'synonyms': None,
			'forms': None,
			'form_type': None,
			'info': info if any(info.values()) else None,
			'aspect_candidates': None,
			'reverse_translation': True,
			'reverse_translation_source_word': source_word,
		})

	for translation in entry.get('translations', []):
		build_translation_entry(translation)

	for sense in entry.get('senses', []):
		if not isinstance(sense, dict):
			continue
		for translation in sense.get('translations', []):
			build_translation_entry(translation, sense_context=sense)

	return parsed_entries


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
			elif entry.get('lang') == 'English':
				reverse_data = _parse_english_translation_entry(entry)
				if reverse_data:
					results.extend(reverse_data)
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


def load_wiktionary_jsonl(kaikki_path, return_aspect_candidates=False):
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

	ukrainian_entries = [pe for pe in parsed_entries if not pe.get('reverse_translation')]
	reverse_entries = [pe for pe in parsed_entries if pe.get('reverse_translation')]
	own_accentless = {
		strip_stress(pe['word'])
		for pe in ukrainian_entries
		if pe.get('word') and (
			pe.get('definitions') or pe.get('forms') or pe.get('info') or pe.get('variants') or pe.get('synonyms')
		)
	}

	words_map = {}
	aspect_pairs = set()
	for pe in ukrainian_entries:
		word_spelling = pe['word']
		pos = pe['pos']
		if not word_spelling:
			continue

		if pe.get('aspect_candidates'):
			for candidate in pe['aspect_candidates']:
				if candidate:
					aspect_pairs.add((word_spelling, candidate))

		if word_spelling not in words_map:
			words_map[word_spelling] = Word(word_spelling)
		w = words_map[word_spelling]

		for d in pe['definitions']:
			if isinstance(d, dict):
				alert_value = d.get('metadata') if d.get('alert') else False
				w.add_definition(
					pos,
					d['definition'],
					alert=alert_value,
					prefix=d.get('prefix'),
					synonyms=d.get('synonyms'),
				)
			else:
				w.add_definition(pos, d)

		if pe.get('synonyms'):
			w.add_synonyms(pe.get('synonyms'))
		if pe.get('variants'):
			w.add_variants(pe['variants'])
		if pe.get('info'):
			w.add_info(pos, pe['info'])
		if pe.get('form_type'):
			w.add_forms(pos, pe.get('forms') or {}, pe['form_type'])

	for pe in reverse_entries:
		word_spelling = pe['word']
		if not word_spelling:
			continue
		if word_spelling in words_map and words_map[word_spelling].usages:
			continue
		if strip_stress(word_spelling) in own_accentless:
			continue
		pos = pe['pos']
		reverse_word = pe.get('reverse_translation_source_word')
		if word_spelling not in words_map:
			words_map[word_spelling] = Word(word_spelling)
		w = words_map[word_spelling]
		for d in pe['definitions']:
			if isinstance(d, dict):
				alert_value = d.get('metadata') if d.get('alert') else False
				w.add_definition(
					pos,
					d['definition'],
					alert=alert_value,
					prefix=d.get('prefix'),
					synonyms=d.get('synonyms'),
					reverse_translation=True,
					reverse_translation_source_word=reverse_word,
				)
			else:
				w.add_definition(
					pos,
					d,
					reverse_translation=True,
					reverse_translation_source_word=reverse_word,
			)
		if pe.get('info'):
			w.add_info(pos, pe['info'])

	if return_aspect_candidates:
		return list(words_map.values()), aspect_pairs
	return list(words_map.values())
