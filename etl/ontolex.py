import os
import json
import extract
from dictionary import Word, Dictionary

DATA_DIR = os.environ.get('DATA_DIR', 'cache')
os.makedirs(DATA_DIR, exist_ok=True)

def _resolve_data_path(loc):
    return loc if os.path.isabs(loc) else os.path.join(DATA_DIR, loc)

class Ontolex_Word:

	def __init__(self, word, data=None):
		self.word = word
		if data:
			self.data = data
		else:
			self.data = {}

	def add_gloss(self, gloss, part_of_speech, can_exist=False):
		definition, translation = None, []
		part_of_speech = part_of_speech.lower() if part_of_speech is not None else None
		if gloss in self.data:
			definition, translation = self.data[gloss]['def'], self.data[gloss]['translation']
		if can_exist or gloss not in self.data:
			self.data[gloss] = {
				'pos': part_of_speech,
				'def': definition,
				'translation': translation
			}

	def add_translation(self, gloss, translation):
		if translation.endswith(' f') or translation.endswith(' m'):
			translation = translation.replace(' f', '(female form)')
			translation = translation.replace(' m', '(male form)')
		self.data[gloss]['translation'].append(translation)
	
	def add_definition(self, gloss, definition):
		self.data[gloss]['def'] = definition

	def get_translations(self):
		results = {}
		for _, gloss_data in self.data.items():
			pos, definition, translations = gloss_data['pos'], gloss_data['def'], gloss_data['translation']
			for t in translations:
				if t in results:
					w = results[t]
				else:
					w = Word(t)
					results[t] = w
				if not definition:
					definition = self.word
				if self.word not in definition:
					w.add_definition(pos, f"{self.word} ({definition})")
				else:
					w.add_definition(pos, definition)
		return list(results.values())

	def get_dict(self):
		return self.data
			

class Ontolex:

	def __init__(self, use_cache=True, use_raw_cache=True, raw_dbnary_path=None):	
		if not raw_dbnary_path:
			raise ValueError('raw_dbnary_path is required')
		self.words = {}	
		cache_path = os.path.join(DATA_DIR, 'ontolex_data.json')
		if use_cache:
			try:
				with open(cache_path, 'r', encoding='utf-8') as f:
					data = json.loads(f.read())
				for w, o_w in data.items():
					self.words[w] = Ontolex_Word(w, o_w)
				return
			except Exception:
				pass
		extract.get_ontolex(use_cache=use_raw_cache, raw_dbnary_path=raw_dbnary_path)
		self.parse_ontolex(raw_dbnary_path)
		self.dump('ontolex_data.json', indent=2)

	def get_word(self, word):
		if word not in self.words:
			self.words[word] = Ontolex_Word(word)
		return self.words[word]

	def parse_ontolex(self, raw_dbnary_path=None):
		if not raw_dbnary_path:
			raise ValueError('raw_dbnary_path is required')
		print('parsing ontolex data (streaming mode)')
		if not os.path.exists(raw_dbnary_path):
			raise FileNotFoundError(f"{raw_dbnary_path} not found")
		
		word, new_word, gloss = None, None, None
		
		with open(raw_dbnary_path, 'r', encoding='utf-8-sig') as f:
			for i, line in enumerate(f):
				if i % 1000000 == 0 and i > 0:
					print(f"Processed {i // 1000000}M lines...")
				
				if 'eng:__en_gloss' in line or 'eng/__en_gloss' in line:
					parts = line.split(';')
					if parts:
						subparts = parts[0].split('>')
						if subparts:
							url_parts = subparts[0].split('/')
							if url_parts:
								nodes = url_parts[-1].split(':')
								gloss = nodes[-1].strip()
								vals = [x.replace('_', ' ').strip() for x in '_'.join(gloss.split('_')[5:]).split('__')]
								if vals:
									word = vals[0]
									new_word = word
									part_of_speech = vals[1] if len(vals) > 1 else None
									self.get_word(word).add_gloss(gloss, part_of_speech)
				
				if 'dbnary:isTranslationOf' in line:
					parts = line.split(';')
					if parts:
						subparts = parts[0].split('>')
						if subparts:
							url_parts = subparts[0].split('/')
							if url_parts:
								nodes = url_parts[-1].split(':')
								translation = nodes[-1].strip().replace('__en_gloss', '')
								vals = [x.replace('_', ' ').strip() for x in translation.split('__')]
								if vals:
									new_word = vals[0]
									if new_word == word and gloss:
										part_of_speech = vals[1] if len(vals) > 1 else None
										self.get_word(word).add_gloss(gloss, part_of_speech)

				if '@uk' in line:
					parts = line.split('@')
					if parts:
						trans_quote = parts[0].replace('\\\"', '*').split("\"")
						if len(trans_quote) > 1:
							translation = trans_quote[1].replace('*', '\\\"').replace('[','').replace(']','')
							translation = " ".join([x.split('|')[0] for x in translation.split(' ')])
							if new_word == word and gloss:
								self.get_word(word).add_translation(gloss, translation)
				
				if 'rdf:value' in line and "@en" in line and '[' not in line:
					parts = line.split('@')
					if parts:
						def_quote = parts[0].replace('\\\"', '*').split("\"")
						if len(def_quote) > 1:
							definition = def_quote[1].replace('*', '\\\"')
							if new_word == word and gloss:
								self.get_word(word).add_definition(gloss, definition)
		print('parsing complete')

	
	def get_dictionary(self, kaikki_path=None, frequency_csv_path=None, deletion_log_path=None):
		dict = Dictionary(
			kaikki_path=kaikki_path,
			frequency_csv_path=frequency_csv_path,
			deletion_log_path=deletion_log_path,
		)
		for _, word in self.words.items():
			translations = word.get_translations()
			dict.add_to_dictionary(translations)
		return dict

	def get_dict(self):
		d = {}
		for w in self.words:
			d[w] = self.words[w].get_dict()
		return d

	def dump(self, loc, indent=None):
		dump_path = _resolve_data_path(loc)
		with open(dump_path, 'w+', encoding='utf-8') as f:
			if indent:
				f.write(
					json.dumps(self.get_dict(), indent=indent, ensure_ascii=False)
				)
			else:
				f.write(
					json.dumps(self.get_dict(), ensure_ascii=False)
				)
