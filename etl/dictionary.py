import os
import json
import re
import unicodedata
from copy import deepcopy
from collections import defaultdict
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from helpers import strip_stress

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
				base_forms[strip_stress(f)] = max(base_forms[strip_stress(f)], f.count("́"))
			new_form_list = []
			for f in form_list:
				if f.count("́") == base_forms[strip_stress(f)]:
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
			if 'inf' in self.forms:
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
		self.def_prefixes = {}  # Store prefixes mapped by definition string
		self.def_synonyms = {}  # Store synonyms mapped by definition string
		self.synonyms = []
		self.frequency = None
		self.forms = {}
		# Structured grammatical tags instead of raw strings
		self.gender = None  # 'male', 'female', 'neuter', or None
		self.animacy = None  # 'animate', 'inanimate', or None
		self.aspect = None  # 'imperfective', 'perfective', or None
		self.reverse_translation = False
		self.reverse_translation_source_word = None
		self.delete_me = False

	def add_definitions(self, definitions):
		for d in definitions:
			self.add_definition(d)

	def add_definition(self, definition, replaced=None, alert=False, prefix=None, synonyms=None, reverse_translation=False, reverse_translation_source_word=None):
		metadata = None
		if isinstance(alert, dict):
			metadata = alert
			alert = True
		if alert:
			self.alerted_definitions[definition] = metadata or {}
		self.definitions[definition] = replaced
		if prefix is not None:
			self.def_prefixes[definition] = prefix
		if synonyms:
			if definition not in self.def_synonyms:
				self.def_synonyms[definition] = []
			for syn in synonyms:
				if syn not in self.def_synonyms[definition]:
					self.def_synonyms[definition].append(syn)
		if reverse_translation:
			self.reverse_translation = True
			if reverse_translation_source_word:
				self.reverse_translation_source_word = self.reverse_translation_source_word or reverse_translation_source_word

	def _forms_contain_word(self, forms, word):
		if isinstance(forms, dict):
			for value in forms.values():
				if self._forms_contain_word(value, word):
					return True
		elif isinstance(forms, list):
			if word in forms:
				return True
			accentless_word = strip_stress(word)
			for form in forms:
				if strip_stress(form) == accentless_word:
					return True
		return False

	def _definition_key(self, definition):
		return strip_stress(definition)

	def _usage_contains_form(self, usage):
		return self._forms_contain_word(usage.get_forms(final_forms=True), self.word)

	def clean_alerted_words(self, dictionary):
		for d in list(self.alerted_definitions.keys()):
			alert_info = self.alerted_definitions.get(d)
			metadata = alert_info if isinstance(alert_info, dict) else None
			relations = set(metadata.get('relations', [])) if metadata else set()
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
					for dd in list(self.alerted_definitions.keys()):
						alert_info = self.alerted_definitions.get(dd)
						metadata = alert_info if isinstance(alert_info, dict) else None
						relations = set(metadata.get('relations', [])) if metadata else set()
						if 'form_of' in relations:
							self.definitions.pop(dd, None)
							self.alerted_definitions.pop(dd, None)
							self.def_prefixes.pop(dd, None)
					continue
				if relations == {'form_of'}:
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
			self.def_prefixes.pop(d, None)

	def add_info(self, info):
		"""Add grammar info from structured source tags."""
		if not info:
			return

		gender = info.get('gender')
		if self.gender is None and gender in ('male', 'female', 'neuter'):
			self.gender = gender

		animacy = info.get('animacy')
		if self.animacy is None and animacy in ('animate', 'inanimate'):
			self.animacy = animacy

		aspect = info.get('aspect')
		if self.aspect is None and aspect in ('imperfective', 'perfective'):
			self.aspect = aspect

	def get_grammar_info(self):
		return {
			'gender': self.gender,
			'animacy': self.animacy,
			'aspect': self.aspect,
		}

	def _word_info_matches_pos(self, word_info, form_type):
		"""Check if inflection form_type is applicable to this usage's POS."""
		return self.pos == form_type


	def get_info(self):
		"""Formatted grammar info string for display."""
		parts = []
		if self.gender:
			parts.append(self.gender)
		if self.animacy:
			parts.append(self.animacy)
		if self.aspect:
			parts.append(self.aspect)
		return ', '.join(parts) if parts else ''

	def add_forms(self, forms, form_type):
		if form_type in self.forms:
			self.forms[form_type].add_forms(forms)
		else:
			forms = Forms(forms, form_type)
			self.forms[form_type] = forms

	def add_synonyms(self, synonyms):
		for syn in synonyms or []:
			if syn not in self.synonyms:
				self.synonyms.append(syn)

	def add_frequency(self, frequency):
		self.frequency = frequency

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
					if self._word_info_matches_pos(word_info, form_type):
						self.add_info(word_info)
						self.add_forms(forms, form_type)
						added_flag = True
						self.delete_me = False
				elif self._word_info_matches_pos(word_info, form_type):
					this_inflection = get_inflection_positions(self.word) 
					found_inflection = get_inflection_positions(found_word)
					if len([x for x in this_inflection if x not in found_inflection]) == 0:  # stress could be elsewhere
						new_usage = Usage(found_word, self.pos)
						new_usage.definitions = deepcopy(self.definitions)
						new_usage.alerted_definitions = deepcopy(self.alerted_definitions)
						new_usage.def_prefixes = deepcopy(self.def_prefixes)
						new_usage.add_info(word_info)
						new_usage.add_forms(forms, form_type)
						new_usages.append(new_usage)
						added_flag = True
						self.delete_me = False
			elif force:
				if self.word == found_word:
					if self.pos in ('noun', 'verb', 'adjective') and self.pos != form_type:
						new_usage = Usage(self.word, form_type)
						new_usage.definitions = deepcopy(self.definitions)
						new_usage.alerted_definitions = deepcopy(self.alerted_definitions)
						new_usage.def_prefixes = deepcopy(self.def_prefixes)
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
			d = strip_stress(d)
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
				f = strip_stress(f)
				f = re.sub(r"[^\w']+", ' ', f).strip().split()
				results += f
		return results

	def merge(self, other, accept_alerts=True, use_other_forms=True):
		new_usage = Usage(self.word, self.pos)
		new_usage.add_synonyms(self.synonyms)
		new_usage.add_synonyms(other.synonyms)
		these_definitions = self.get_definitions()
		other_definitions = other.get_definitions()
		min_length = min(len(these_definitions), len(other_definitions))
		for pair in zip(self.get_definitions(), other.get_definitions(accept_alerts)):
			self_alert = self.alerted_definitions.get(pair[0], False)
			other_alert = other.alerted_definitions.get(pair[1], False)
			self_prefix = self.def_prefixes.get(pair[0])
			other_prefix = other.def_prefixes.get(pair[1])
			self_synonyms = self.def_synonyms.get(pair[0])
			other_synonyms = other.def_synonyms.get(pair[1])
			new_usage.add_definition(
				pair[0],
				alert=self_alert,
				prefix=self_prefix,
				synonyms=self_synonyms,
			)
			new_usage.add_definition(
				pair[1],
				alert=other_alert,
				prefix=other_prefix,
				synonyms=other_synonyms,
			)
		if len(these_definitions) > len(other_definitions):
			for d in these_definitions[-1 * (len(these_definitions) - min_length):]:
				prefix = self.def_prefixes.get(d)
				self_synonyms = self.def_synonyms.get(d)
				new_usage.add_definition(
					d,
					alert=self.alerted_definitions.get(d, False),
					prefix=prefix,
					synonyms=self_synonyms,
				)
		elif len(other_definitions) > len(these_definitions):
			for d in other_definitions[-1 * (len(other_definitions) - min_length):]:
				prefix = other.def_prefixes.get(d)
				other_synonyms = other.def_synonyms.get(d)
				new_usage.add_definition(
					d,
					alert=other.alerted_definitions.get(d, False),
					prefix=prefix,
					synonyms=other_synonyms,
				)
		self.definitions = new_usage.definitions
		self.alerted_definitions = new_usage.alerted_definitions
		self.def_prefixes = new_usage.def_prefixes
		self.def_synonyms = new_usage.def_synonyms
		if use_other_forms:
			for ft, forms in other.forms.items():
				if ft in self.forms:
					self.forms[ft].add_forms(forms.forms)
				else:
					self.forms[ft] = forms
			# Merge grammatical tags: prefer self's tags, fall back to other's
			if self.gender is None and other.gender is not None:
				self.gender = other.gender
			if not self.animacy and other.animacy:
				self.animacy = other.animacy
			if not self.aspect and other.aspect:
				self.aspect = other.aspect
		# Preserve reverse translation metadata when one of the merged usages is reverse translation.
		if self.reverse_translation or other.reverse_translation:
			self.reverse_translation = True
			self.reverse_translation_source_word = self.reverse_translation_source_word or other.reverse_translation_source_word
		# Merge prefixes
		for def_str, prefix in other.def_prefixes.items():
			if def_str not in self.def_prefixes:
				self.def_prefixes[def_str] = prefix

	def get_dict(self, final_forms=False):
		defs = []
		prefixes = []
		def_synonyms = []
		for d, pov in self.definitions.items():
			definition = d
			if pov and pov not in d:
				definition = f"{d} ({pov})"
			metadata = self.alerted_definitions.get(d)
			relations = set(metadata.get('relations', [])) if isinstance(metadata, dict) else set()
			if relations == {'form_of'}:
				continue
			defs.append(definition)
			prefixes.append(self.def_prefixes.get(d))
			def_synonyms.append(self.def_synonyms.get(d) or [])
		result = {
			'defs': defs,
			'freq': self.frequency,
			'info': self.get_info(),
			'grammar': {
				'gender': self.gender,
				'animacy': self.animacy,
				'aspect': self.aspect,
			},
			'forms': self.get_forms(final_forms)
		}
		if self.synonyms:
			result['synonyms'] = self.synonyms
		if any(def_synonyms):
			result['def_synonyms'] = def_synonyms
		if self.reverse_translation:
			result['reverse_translation'] = True
			if self.reverse_translation_source_word:
				result['reverse_translation_source_word'] = self.reverse_translation_source_word
		# Only include def_prefixes if there are any non-None values
		if any(p is not None for p in prefixes):
			result['def_prefixes'] = prefixes
		return result


class Word:


	def __init__(self, word):
		if word == "будова (bud'''o'''wa)":
			word = 'будова'
		self.word = word
		self.word_no_accent = strip_stress(self.word)
		self.usages = {}
		self.variants = []
		self.synonyms = []

	def normalize_pos(pos):
		replace = {
			'letter': 'noun',
			'number': 'numeral',
			'numeral': 'numeral',
			'prepositional phrase': 'phrase',
			'name': 'noun',
			'proper noun': 'noun',
			'det': 'particle',
		}
		if pos in replace:
			return replace[pos]
		if not pos:
			pos = 'particle'
		return pos

	def get_word_no_accent(self):
		return self.word_no_accent

	def add_definition(self, pos, definition, alert=False, prefix=None, synonyms=None, reverse_translation=False, reverse_translation_source_word=None):
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
		if self.synonyms:
			u.add_synonyms(self.synonyms)
		u.add_definition(
			definition,
			replaced=replaced,
			alert=alert,
			prefix=prefix,
			synonyms=synonyms,
			reverse_translation=reverse_translation,
			reverse_translation_source_word=reverse_translation_source_word
		)

	def add_variants(self, variants):
		if not variants:
			return
		for variant in variants:
			if variant and variant != self.word and variant not in self.variants:
				self.variants.append(variant)

	def add_variant(self, variant):
		self.add_variants([variant])

	def add_synonyms(self, synonyms):
		for syn in synonyms or []:
			if syn not in self.synonyms:
				self.synonyms.append(syn)
		for usage in self.usages.values():
			usage.add_synonyms(synonyms)

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
				variants = sorted(
					set(self.variants),
					key=lambda x: (strip_stress(x), x),
				)
				base = self.get_word_no_accent()
				if base != self.word:
					variants = [v for v in variants if v != base]
				if variants:
					result['variants'] = variants
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
		self.verb_aspect_counterparts: Optional[Dict[int, List[int]]] = None
		self.verb_aspect_candidate_pairs: Set[Tuple[str, str]] = set()

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
			words, candidate_pairs = extract.load_wiktionary_jsonl(self.kaikki_path, return_aspect_candidates=True)
			self.verb_aspect_candidate_pairs = candidate_pairs
			for w in words:
				self.add_to_dictionary(w)
		except Exception as e:
			raise e
		print('done parsing wiktionary data')
		self.clean_alerted_words()
		self.garbage_collect()
		self.add_frequencies()
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

	def add_verb_aspect_counterparts(self, known_pairs_path=None):
		from build_verb_aspect_map import build_verb_counterpart_map

		known_pairs_path = Path(known_pairs_path) if known_pairs_path is not None else None
		candidate_pairs = self.verb_aspect_candidate_pairs
		self.verb_aspect_counterparts = build_verb_counterpart_map(
			self,
			known_pairs_path=known_pairs_path,
			candidate_pairs=candidate_pairs,
		)

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
		normalized = strip_stress(query)
		candidates = set()
		if query in self.dict:
			candidates.add(query)
		if normalized in self.accentless_words:
			candidates.update(self.accentless_words[normalized])
		if candidates:
			return sorted(candidates)

		cleaned_query = re.sub(r"\s*\b(pf|impf|perfective|imperfective)\b\s*$", '', query, flags=re.IGNORECASE).strip()
		if cleaned_query and cleaned_query != query:
			cleaned_normalized = strip_stress(cleaned_query)
			if cleaned_query in self.dict:
				candidates.add(cleaned_query)
			if cleaned_normalized in self.accentless_words:
				candidates.update(self.accentless_words[cleaned_normalized])
		return sorted(candidates)

	def _matching_deletions(self, query: str) -> List[Dict[str, Optional[str]]]:
		normalized = strip_stress(query)
		return [
			deletion for deletion in self.deletions
			if deletion['word'] == query or strip_stress(deletion['word']) == normalized
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

		max_freq = max([x['freq'] if x['freq'] is not None else -1 for x in result])
		result = sorted(
			result,
			key=lambda x: (
				x['freq'] if x['freq'] is not None else max_freq + 1,
				len(x['word']),
			)
		)
		for i, r in enumerate(result):
			r['index'] = i
		index_by_word = {}
		for i, r in enumerate(result):
			if r['word'] not in index_by_word:
				index_by_word[r['word']] = i
			accentless_word = strip_stress(r['word'])
			if accentless_word not in index_by_word:
				index_by_word[accentless_word] = i

		def _resolve_synonym_target(synonym):
			if isinstance(synonym, int):
				return synonym
			candidates = self._find_word_candidates(str(synonym))
			for candidate in candidates:
				if candidate in index_by_word:
					return index_by_word[candidate]
			return None

		for r in result:
			if 'synonyms' in r:
				resolved = []
				for item in r['synonyms']:
					if isinstance(item, int):
						resolved.append(item)
					else:
						target = _resolve_synonym_target(item)
						resolved.append(target if target is not None else item)
				r['synonyms'] = resolved
			if 'def_synonyms' in r:
				resolved_defs = []
				for syn_list in r['def_synonyms']:
					resolved_items = []
					for item in syn_list:
						if isinstance(item, int):
							resolved_items.append(item)
						else:
							target = _resolve_synonym_target(item)
							resolved_items.append(target if target is not None else item)
					resolved_defs.append(resolved_items)
				r['def_synonyms'] = resolved_defs
		if self.verb_aspect_counterparts:
			for r in result:
				counterparts = self.verb_aspect_counterparts.get(r['index'])
				if counterparts:
					r['counterparts'] = counterparts
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
