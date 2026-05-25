import os
import json
import re
from copy import deepcopy
from collections import defaultdict
from enum import Enum
from typing import Dict, List, Optional

DATA_DIR = os.environ.get('DATA_DIR', 'cache')
os.makedirs(DATA_DIR, exist_ok=True)

def _resolve_data_path(loc):
    return loc if os.path.isabs(loc) else os.path.join(DATA_DIR, loc)

cyrillic = "ЄІЇАБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдежзийклмнопрстуфхцчшщъыьэюяєії"


class DeletionReason(Enum):
	NO_DEFINITIONS = 'no_more_defs'
	INVALID_INFLECTION = 'invalid_inflection'
	BAD_POS = 'bad_pos'

class Forms:
	
	def __init__(self, forms, form_type):
		self.forms = {}
		self.add_forms(forms)
		self.form_type = form_type
		
	def add_forms(self, forms):
		if forms: 
			if self.forms:
				for key in (self.forms.keys() | forms.keys()):
					these_forms = []
					other_forms = []
					if key in self.forms:
						these_forms = self.forms[key]
					if key in forms:
						other_forms = forms[key]
					surplus = []
					if len(these_forms) < len(other_forms):
						surplus = other_forms[len(these_forms):]
					elif len(these_forms) > len(other_forms):
						surplus = these_forms[len(other_forms):]
					self.forms[key] = [x for pair in zip(these_forms, other_forms) for x in pair] + surplus
			else:
				self.forms = forms

		# remove duplicates
		for form_id in self.forms:
			form_list = self.forms[form_id]
			new_form_list = {form.replace('*', ''): None for form in form_list}
			self.forms[form_id] = [x for x in new_form_list]

		# remove unaccented forms when an accented form exists
		for form_id in self.forms:
			form_list = self.forms[form_id]
			base_forms = defaultdict(lambda: 0)
			for f in form_list:
				base_forms[f.replace("́", "")] = max(base_forms[f.replace("́", "")], f.count("́")) 
			new_form_list = []
			for f in form_list:
				if f.count("́") == base_forms[f.replace("́", "")]:
					new_form_list.append(f)
			self.forms[form_id] = new_form_list

	def get_final_forms(self):
		if self.form_type not in ('verb', 'adj'):
			return self.forms
		elif self.form_type == 'adj':
			new_forms = defaultdict(lambda: {})
			for form in self.forms:
				if 'addl' in form:
					new_forms['addl'][form.split()[1]] = self.forms[form]
				else:
					new_forms[form] = self.forms[form]
			new_forms = dict(new_forms)
			return new_forms
		else:
			new_forms = defaultdict(lambda: defaultdict(lambda: {}))
			for form in [x for x in self.forms if x != 'inf']:
				info = form.split(' ')
				if len(info) == 2:
					new_forms[info[0]][info[1]] = self.forms[form]
				elif len(info) == 3:
					new_forms[info[0]]['pp'][info[1]] = self.forms[form]
			new_forms['inf'] = self.forms['inf']
			for form in new_forms:
				if isinstance(new_forms[form], defaultdict):
					new_forms[form] = dict(new_forms[form])
			return new_forms


class Usage:

	def __init__(self, word, pos):
		self.word = word
		if not pos:
			pos = 'particle'
		self.pos = pos
		self.definitions = {}
		self.alerted_definitions = {}
		self.frequency = None
		self.forms = {}
		self.info = {}
		self.delete_me = False

	def add_definitions(self, definitions):
		for d in definitions:
			self.add_definition(d)

	def add_definition(self, definition, replaced=None, alert=False):
		metadata = None
		if isinstance(alert, dict):
			metadata = alert
			alert = True
		if alert:
			self.alerted_definitions[definition] = metadata or {}
		self.definitions[definition] = replaced
		# check to ensure definitions are not redundant
		bad_defs = set()
		for d1 in self.definitions.keys():
			for d2 in self.definitions.keys():
				new_d = ''
				parenthesis = 0
				for d in d2:
					if d == '(':
						parenthesis += 1
					if parenthesis == 0:
						new_d += d
					if d == ')':
						parenthesis -= 1
				if d1 != d2 and d1.lower() in new_d.lower():
					bad_defs.add(d1)
		for d in bad_defs:
			self.definitions.pop(d, None)
			self.alerted_definitions.pop(d, None)

	def _forms_contain_word(self, forms, word):
		if isinstance(forms, dict):
			for value in forms.values():
				if self._forms_contain_word(value, word):
					return True
		elif isinstance(forms, list):
			if word in forms:
				return True
			accentless_word = word.replace('́', '')
			for form in forms:
				if form.replace('́', '') == accentless_word:
					return True
		return False

	def _usage_contains_form(self, usage):
		return self._forms_contain_word(usage.get_forms(final_forms=True), self.word)

	def clean_alerted_words(self, dictionary):
		for d in list(self.alerted_definitions.keys()):
			alert_info = self.alerted_definitions.get(d)
			metadata = alert_info if isinstance(alert_info, dict) else None
			relations = set()
			if metadata:
				relations.update(metadata.get('relations', []))
			if 'form_of' in relations:
				resolved = False
				for target in metadata.get('targets', []):
					for candidate in dictionary._find_word_candidates(target):
						matched_word = dictionary.dict.get(candidate)
						if matched_word and self.pos in matched_word.usages:
							lemma_usage = matched_word.usages[self.pos]
							if self._usage_contains_form(lemma_usage):
								resolved = True
								break
					if resolved:
						break
				if resolved:
					for d in list(self.alerted_definitions.keys()):
						alert_info = self.alerted_definitions.get(d)
						metadata = alert_info if isinstance(alert_info, dict) else None
						relations = set(metadata.get('relations', [])) if metadata else set()
						if 'form_of' in relations:
							self.definitions.pop(d, None)
							self.alerted_definitions.pop(d, None)
					continue
				if relations - {'form_of'}:
					continue
				continue
			elif relations:
				continue
			found_word = ''
			for x in d:
				if x in cyrillic + ' ' + "'" + "́":
					found_word = found_word + x
			found_words = re.sub(r"[^\ẃ]+", ' ', found_word).strip().split()
			nothing_found = True
			for found_word in found_words:
				for candidate in dictionary._find_word_candidates(found_word):
					matched_word = dictionary.dict.get(candidate)
					if matched_word and self.pos in matched_word.usages:
						matched_word.usages[self.pos].merge(deepcopy(self), accept_alerts=False, use_other_forms=False)
						nothing_found = False
						break
				if not nothing_found:
					break
			if nothing_found:
				self.definitions.pop(d, None)
				self.alerted_definitions.pop(d, None)

	def add_frequency(self, frequency):
		self.frequency = frequency

	def add_info(self, info):
		if info:
			self.info[info] = None

	def get_info(self):
		gender, aspect, animacy = set(), set(), set()
		for info in self.info:
			for word in info.lower().split():
				if word in ('f', 'female', 'feminine'):
					gender.add('female')
				if word in ('m', 'male', 'masculine'):
					gender.add('male')
				if word in ('animal', 'animate', 'anim'):
					animacy.add('animate')
				if word in ('n', 'neuter'):
					gender.add('neuter')
				if word in ('inan', 'inanimate'):
					animacy.add('inanimate')
				if word in ('imperfective', 'impf'):
					aspect.add('imperfective')
				if word in ('pf', 'perfective'):
					aspect.add('perfective')
		new_info = []
		if len(gender) > 0:
			gender = ' or '.join(gender)
			new_info.append(gender)
		if len(aspect) > 0:
			aspect = ' or '.join(aspect)
			new_info.append(aspect)
		if len(animacy) > 0:
			animacy = ' or '.join(animacy)
			new_info.append(animacy)
		if len(new_info) > 0:
			new_info = ", ".join(new_info)
		else:
			new_info = ""
		return new_info

	def add_forms(self, forms, form_type):
		if form_type in self.forms:
			self.forms[form_type].add_forms(forms)
		else:
			forms = Forms(forms, form_type)
			self.forms[form_type] = forms

	def add_inflection(self, results, force=False):

		def get_inflection_positions(word):
			word = word + '|'  # end of word marker, irrelevant
			word_split = [(word[i], word[i+1]) for i in range(len(word) - 1) if word[i] != "́"]
			result = set([i for i in range(len(word_split)) if word_split[i][1] == "́"])
			return result

		added_flag = False
		new_usages = []
		self.delete_me = True
		if all(found_word is None for found_word, *_ in results):
			# No inflection candidates were found in the Wiktionary lookup.
			# Preserve the existing usage instead of deleting it when no data is available.
			self.delete_me = False
			return False, []
		for found_word, word_info, forms, form_type in results:
			if found_word:
				if self.word == found_word: # perfect match!
					if self.pos == form_type or self.pos in word_info:
						self.add_info(word_info)
						self.add_forms(forms, form_type)
						added_flag = True
						self.delete_me = False
				elif self.pos and self.pos in word_info:
					this_inflection = get_inflection_positions(self.word) 
					found_inflection = get_inflection_positions(found_word)
					if len([x for x in this_inflection if x not in found_inflection]) == 0:  # stress could be elsewhere
						new_usage = Usage(found_word, self.pos)
						new_usage.definitions = deepcopy(self.definitions)
						new_usage.alerted_definitions = deepcopy(self.alerted_definitions)
						new_usage.add_info(word_info)
						new_usage.add_forms(forms, form_type)
						new_usages.append(new_usage)
						added_flag = True
			elif force:
				if self.word == found_word:
					if self.pos in ('noun', 'verb', 'adjective') and self.pos != form_type:
						new_usage = Usage(self.word, form_type)
						new_usage.definitions = deepcopy(self.definitions)
						new_usage.alerted_definitions = deepcopy(self.alerted_definitions)
						new_usage.add_info(word_info)
						new_usage.add_forms(forms, form_type)
						new_usages.append(new_usage)
					else:
						self.add_info(word_info)
						self.add_forms(forms, form_type)
						self.delete_me = False
		if self.pos not in ('noun', 'verb', 'adjective'):
			self.delete_me = False
		if not added_flag and len(self.forms) > 0:
			self.delete_me = False
		return not added_flag and len(self.forms) == 0, new_usages

	def get_definitions(self, accept_alerts=True):
		result = []
		for d, pov in self.definitions.items():
			if pov and pov not in d:
				d = f"{d} ({pov})"
			if accept_alerts or d not in self.alerted_definitions:
				result.append(d)
		return result

	def get_forms(self, final_forms=False):
		results = {}
		for form_id in self.forms:
			forms = self.forms[form_id].forms
			if final_forms:
				forms = self.forms[form_id].get_final_forms()
			
			def merge_structures(d1, d2):
				res = dict(d1)
				for k, v in d2.items():
					if k in res:
						if isinstance(res[k], list) and isinstance(v, list):
							merged = list(res[k])
							for item in v:
								if item not in merged:
									merged.append(item)
							res[k] = merged
						elif isinstance(res[k], dict) and isinstance(v, dict):
							res[k] = merge_structures(res[k], v)
						else:
							res[k] = v
					else:
						res[k] = v
				return res

			results = merge_structures(results, forms)
		return results

	def get_definition_words(self):
		results = []
		for d in self.get_definitions():
			d = d.replace('́', '')
			new_d = ''
			parenthesis = 0
			for l in d:
				if l == '(':
					parenthesis += 1
				elif l == ')':
					parenthesis -= 1
				elif parenthesis == 0:
					new_d += l
			d = new_d 
			d = re.sub(r"[^A-Za-z']+", ' ', d).strip().split()
			results += d
		return results

	def get_form_words(self):
		results = []
		for forms in self.get_forms().values():
			for f in forms:
				f = f.replace('́', '')
				f = re.sub(r"[^\w']+", ' ', f).strip().split()
				results += f
		return results

	def merge(self, other, accept_alerts=True, use_other_forms=True):
		new_usage = Usage(self.word, self.pos)
		these_definitions = self.get_definitions()
		other_definitions = other.get_definitions()
		min_length = min(len(these_definitions), len(other_definitions))
		for pair in zip(self.get_definitions(), other.get_definitions(accept_alerts)):
			self_alert = self.alerted_definitions.get(pair[0], False)
			other_alert = other.alerted_definitions.get(pair[1], False)
			new_usage.add_definition(pair[0], alert=self_alert)
			new_usage.add_definition(pair[1], alert=other_alert)
		if len(these_definitions) > len(other_definitions):
			for d in these_definitions[-1 * (len(these_definitions) - min_length):]:
				new_usage.add_definition(d, alert=self.alerted_definitions.get(d, False))
		elif len(other_definitions) > len(these_definitions):
			for d in other_definitions[-1 * (len(other_definitions) - min_length):]:
				new_usage.add_definition(d, alert=other.alerted_definitions.get(d, False))
		self.definitions = new_usage.definitions
		self.alerted_definitions = new_usage.alerted_definitions
		if use_other_forms:
			for ft, forms in other.forms.items():
				if ft in self.forms:
					self.forms[ft].add_forms(forms.forms)
				else:
					self.forms[ft] = forms
			if len(self.info) == 0 and len(other.info) > 0:
				self.info = other.info

	def get_dict(self, final_forms=False):
		return {
			'defs': self.get_definitions(),
			'freq': self.frequency,
			'info': self.get_info(),
			'forms': self.get_forms(final_forms)
		}


class Word:


	def __init__(self, word):
		if word == "будова (bud'''o'''wa)":
			word = 'будова'
		self.word = word
		self.word_no_accent = self.word.replace("́", "")
		self.usages = {}
		self.variants = []

	def normalize_pos(pos):
		replace = {
			'conjunction': 'particle',
			'determiner': 'particle',
			'interjection': 'particle',
			'letter': 'noun',
			'number': 'numeral',
			'numeral': 'numeral',
			'postposition': 'particle',
			'predicative': 'particle',
			'preposition': 'particle',
			'prepositional phrase': 'phrase',
			'name': 'noun',
			'proper noun': 'noun',
		}
		if pos in replace:
			return replace[pos]
		if not pos:
			pos = 'particle'
		return pos

	def get_word_no_accent(self):
		return self.word_no_accent

	def add_definition(self, pos, definition, alert=False):
		if pos is None:
			pos = 'particle'
		if pos == 'verb' and len(definition.split()) == 1:
			definition = f"to {definition}"
		if '[1]' in definition:
			definition = definition.replace('[1]', '')
		elif definition.endswith(']') and '[' not in definition:
			definition = definition[:-1]
		bad_stuff = [
			('“', '"'), 
			('”', '"'), 
			(r'{{', ''), 
			(r'}}', ''), 
			('()', ''), 
			('\u200b', ''), 
			(' :', ':'), 
			('’', "'"),
			(',:', ':'),
			('\\', ''),
			(',)', ')'),
			(',,', ','),
			(', (', ' ('),
			('!slash!', '/')
		]
		for x, y in bad_stuff:
			if x in definition:
				definition = definition.replace(x, y)
		definition = ' '.join(definition.split())
		if 'This term needs a translation to English. Please help out and add a translation, then remove the text' in definition:
			return  # No
		if 'This term needs a translation to English. Please help out and add a translation, then remove the text rfdef.' in definition:
			return # No

		replaced = pos

		pos = Word.normalize_pos(pos)
		if pos == replaced:
			replaced = None

		if pos in self.usages:
			u = self.usages[pos]
		else:
			u = Usage(self.word, pos)
			self.usages[pos] = u
		u.add_definition(definition, replaced=replaced, alert=alert)

	def add_variants(self, variants):
		if not variants:
			return
		for variant in variants:
			if variant and variant != self.word and variant not in self.variants:
				self.variants.append(variant)

	def add_variant(self, variant):
		self.add_variants([variant])

	def merge(self, other):
		for pos, usage in other.usages.items():
			if pos in self.usages:
				self.usages[pos].merge(usage)
			else:
				self.usages[pos] = usage
		self.add_variants(other.variants)
		if other.word != self.word:
			self.add_variant(other.word)

	def clean_alerted_words(self, dictionary):
		for _, usage in self.usages.items():
			usage.clean_alerted_words(dictionary)

	def garbage_collect(self):
		deleted = []
		for pos in list(self.usages.keys()):
			usage = self.usages[pos]
			if len(usage.definitions.keys()) == 0 or usage.delete_me or pos in ('suffix', 'prefix'):
				if(len(usage.definitions.keys()) == 0):
					reason = DeletionReason.NO_DEFINITIONS
				elif usage.delete_me:
					reason = DeletionReason.INVALID_INFLECTION
				elif pos in ('suffix', 'prefix'):
					reason = DeletionReason.BAD_POS
				deleted.append({
					'type': 'usage',
					'word': self.word,
					'pos': pos,
					'reason': reason.value,
					'word_obj': self,
				})
				del self.usages[pos]
		return deleted

	def add_frequencies(self, frequencies):
		normalized_freqs = {}
		if frequencies:
			for pos, rank in frequencies.items():
				normalized_freqs[Word.normalize_pos(pos)] = rank
		for pos, usage in self.usages.items():
			if normalized_freqs and pos in normalized_freqs:
				usage.add_frequency(normalized_freqs[pos])
			else:
				usage.add_frequency(None)

	def add_info(self, pos, word_info):
		pos = Word.normalize_pos(pos)
		if pos in self.usages:
			self.usages[pos].add_info(word_info)

	def add_forms(self, pos, forms, form_type):
		pos = Word.normalize_pos(pos)
		if pos in self.usages:
			self.usages[pos].add_forms(forms, form_type)

	def add_inflections(self, results):
		needs_flag = True
		new_usages = []
		for usage in self.usages.values():
			this_needs, nu = usage.add_inflection(results)
			if not this_needs:
				needs_flag = False
			new_usages += nu
		if needs_flag:
			for usage in self.usages.values():
				_, nu = usage.add_inflection(results, force=True)
				new_usages += nu
		return new_usages

	def get_final_form(self):
		results = []
		for pos, usage in self.usages.items():
			result = {'word': self.word, 'pos': pos}
			if self.variants:
				result['variants'] = sorted(
					set(self.variants),
					key=lambda x: (x.replace('́', ''), x),
				)
			result = {**result, **usage.get_dict(final_forms=True)}
			results.append(result)
		return results

	def get_dict(self):
		dict = {}
		for k, v in self.usages.items():
			dict[k] = v.get_dict()
		return dict


class Dictionary:

	def __init__(self, kaikki_path=None, frequency_csv_path=None, deletion_log_path=None):
		if not kaikki_path:
			raise ValueError('kaikki_path is required')
		if not frequency_csv_path:
			raise ValueError('frequency_csv_path is required')
		self.dict = {}
		self.accentless_words = defaultdict(lambda: set())
		self.kaikki_path = kaikki_path
		self.frequency_csv_path = frequency_csv_path
		self.deletion_log_path = deletion_log_path
		self.deletions = []

	def _handle_no_accent(self, to_add, no_accent):
		existing_keys = list(self.accentless_words[no_accent])
		if no_accent == to_add.word:
			# Accentless entries should merge into an existing accented candidate,
			# unless no accented variant exists yet.
			if no_accent in self.dict:
				self.dict[no_accent].merge(to_add)
				return

			for k in existing_keys:
				if k != no_accent and k in self.dict:
					self.dict[k].merge(to_add)
					self.dict[k].add_variant(to_add.word)
					self.accentless_words[no_accent].add(to_add.word)
					return

			self.dict[to_add.word] = to_add
			self.accentless_words[no_accent].add(to_add.word)
		else:
			# If an accentless-only placeholder already exists, merge it into the
			# new accented variant instead of keeping a separate word key.
			if no_accent in self.dict:
				accentless_entry = self.dict[no_accent]
				to_add.merge(accentless_entry)
				to_add.add_variant(accentless_entry.word)
				del self.dict[no_accent]
				self.accentless_words[no_accent].discard(no_accent)

			self.dict[to_add.word] = to_add
			self.accentless_words[no_accent].add(to_add.word)

	def _add_word_to_dictionary(self, to_add):
		if to_add.word in self.dict:
			self.dict[to_add.word].merge(to_add)
		else:
			no_accent = to_add.get_word_no_accent()
			if no_accent in self.accentless_words:
				self._handle_no_accent(to_add, no_accent)
			else:
				self.dict[to_add.word] = to_add		
				self.accentless_words[no_accent].add(to_add.word)

	def add_to_dictionary(self, to_add):
		if isinstance(to_add, Word):
			self._add_word_to_dictionary(to_add)
		if isinstance(to_add, list):
			for w in to_add:
				self._add_word_to_dictionary(w)

	def add_wiktionary_words(self):
		import extract
		print("adding wiktionary words")
		print('parsing wiktionary data from jsonl')
		try:
			words = extract.load_wiktionary_jsonl(self.kaikki_path)
			for w in words:
				self.add_to_dictionary(w)
		except Exception as e:
			raise e
		print('done parsing wiktionary data')
		self.clean_alerted_words()
		self.garbage_collect()
		self.add_frequencies()
		self.get_inflections()
		self.garbage_collect()

	def clean_alerted_words(self):
		for _, w in self.dict.items():
			w.clean_alerted_words(self)

	def garbage_collect(self):
		for w in list(self.dict.keys()):
			word = self.dict[w]
			deleted = word.garbage_collect()
			self.deletions.extend(deleted)
			if len(word.usages.keys()) == 0:
				self.deletions.append({
					'type': 'word',
					'word': w,
					'pos': None,
					'reason': DeletionReason.NO_DEFINITIONS.value,
					'word_obj': word,
				})
				del self.dict[w]

	def add_frequencies(self):
		import extract
		frequencies = extract.get_frequency_list(self.frequency_csv_path)
		for _, word in self.dict.items():
			if word.get_word_no_accent() in frequencies:
				word.add_frequencies(frequencies[word.get_word_no_accent()])
			else:
				word.add_frequencies(None)

	def get_inflections(self):
		import extract
		print("getting inflections")
		try:
			n = len(self.dict.values())
			for i, word in enumerate(list(self.dict.keys())):
				if i % 1000 == 0:
					print(f"{i} of {n}")
				w = self.dict[word]
				results = extract.get_inflection(w, self.kaikki_path)
				new_usages = w.add_inflections(results)
				for n_u in new_usages:
					new_w = Word(n_u.word)
					new_w.usages[n_u.pos] = n_u
					self.add_to_dictionary(new_w)
		except Exception as e:
			raise e
		finally:
			extract.dump_inflection_cache()

	def get_dict(self):
		dict = {}
		for k, v in self.dict.items():
			dict[k] = v.get_dict()
		return dict

	def write_deletion_log(self):
		if not self.deletion_log_path:
			return

		serializable_deletions = []
		filtered_deletions = []
		for deletion in self.deletions:
			entry = {k: v for k, v in deletion.items() if k != 'word_obj'}
			serializable_deletions.append(entry)
			if not self._should_filter_deletion(deletion):
				filtered_deletions.append(entry)

		with open(self.deletion_log_path, 'w', encoding='utf-8') as f:
			json.dump(serializable_deletions, f, ensure_ascii=False, indent=2)

		filtered_path = self._get_filtered_deletion_path()
		with open(filtered_path, 'w', encoding='utf-8') as f:
			json.dump(filtered_deletions, f, ensure_ascii=False, indent=2)

		print(
			f"wrote {len(serializable_deletions)} deletions to {self.deletion_log_path} "
			f"and {len(filtered_deletions)} filtered deletions to {filtered_path}"
		)

	def _get_filtered_deletion_path(self):
		base = os.path.splitext(self.deletion_log_path)[0]
		return f"{base}.filtered.json"

	def _should_filter_deletion(self, deletion):
		word_obj = deletion.get('word_obj')
		if not word_obj:
			return False
		accentless = word_obj.get_word_no_accent()
		if accentless not in self.accentless_words:
			return False
		for candidate in self.accentless_words[accentless]:
			if candidate in self.dict:
				return True
		return False

	def _find_word_candidates(self, query: str) -> List[str]:
		normalized = query.replace('́', '')
		candidates = set()
		if query in self.dict:
			candidates.add(query)
		if normalized in self.accentless_words:
			candidates.update(self.accentless_words[normalized])
		if candidates:
			return sorted(candidates)

		cleaned_query = re.sub(r"\s*\b(pf|impf|perfective|imperfective)\b\s*$", '', query, flags=re.IGNORECASE).strip()
		if cleaned_query and cleaned_query != query:
			cleaned_normalized = cleaned_query.replace('́', '')
			if cleaned_query in self.dict:
				candidates.add(cleaned_query)
			if cleaned_normalized in self.accentless_words:
				candidates.update(self.accentless_words[cleaned_normalized])
		return sorted(candidates)

	def _matching_deletions(self, query: str) -> List[Dict[str, Optional[str]]]:
		normalized = query.replace('́', '')
		return [
			deletion for deletion in self.deletions
			if deletion['word'] == query or deletion['word'].replace('́', '') == normalized
		]

	def get_debug_info(self, query_words: List[str]) -> Dict[str, object]:
		return {
			'word_count': len(self.dict),
			'final_form_count': len(self.get_final_forms()),
			'queries': [
				{
					'query': query,
					'candidates': [
						{
							'word': candidate,
							'usages': {
								pos: usage.get_dict(final_forms=True)
								for pos, usage in self.dict[candidate].usages.items()
							}
						}
					for candidate in self._find_word_candidates(query)
					if candidate in self.dict
				],
				'deletions': self._matching_deletions(query),
			}
			for query in query_words
		]}

	def get_final_forms(self):
		result = []
		for word in self.dict:
			result += self.dict[word].get_final_form()

		max_freq = max([x['freq'] if x['freq'] else -1 for x in result])
		result = sorted(
			result, 
			key=lambda x: (
				x['freq'] if x['freq'] is not None else max_freq + 1, 
				len(x['word']), 
				x['word']
			)
		)
		for i, r in enumerate(result):
			r['index'] = i
		return result

	def make_index(self, loc1, loc2, indent=None):
		data = self.get_final_forms()
		word_index = defaultdict(lambda: set())
		for i, d in enumerate(data):
			word = self.dict[d['word']]
			usage = word.usages[d['pos']]
			def_words = usage.get_definition_words()
			form_words = usage.get_form_words() + re.sub(r"[^\w']+", ' ', word.get_word_no_accent()).strip().split()
			for d in def_words:
				d = d.lower().replace('ї', 'і').replace('ґ', 'г')
				word_index[d].add(i)
			for f in form_words:
				f = f.lower().replace('ї', 'і').replace('ґ', 'г')
				word_index[f].add(i)

		word_index_list = {}
		word_part = defaultdict(lambda: set())
		for i, word in enumerate(list(word_index.keys())):
			word_index_list[i] = [word, list(word_index[word])]
			for l in word:
				word_part[l].add(i)
		for i in word_part:
			word_part[i] = list(word_part[i])

		with open(_resolve_data_path(loc1), 'w+', encoding='utf-8') as f:
			if indent:
				f.write(
					json.dumps(word_index_list, indent=indent, ensure_ascii=False)
				)
			else:
				f.write(
					json.dumps(word_index_list, ensure_ascii=False)
				)

		with open(_resolve_data_path(loc2), 'w+', encoding='utf-8') as f:
			if indent:
				f.write(
					json.dumps(word_part, indent=indent, ensure_ascii=False)
				)
			else:
				f.write(
					json.dumps(word_part, ensure_ascii=False)
				)

	def dump(self, loc, indent=None, final_form=False):
		if final_form:
			data = self.get_final_forms()
		else:
			data = self.get_dict()

		with open(_resolve_data_path(loc), 'w+', encoding='utf-8') as f:
			if indent:
				f.write(
					json.dumps(data, indent=indent, ensure_ascii=False)
				)
			else:
				f.write(
					json.dumps(data, ensure_ascii=False)
				)