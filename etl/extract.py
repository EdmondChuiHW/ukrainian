import os
import re
import json
import multiprocessing
import threading
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from collections import defaultdict
from copy import deepcopy
from functools import lru_cache
from typing import Optional

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, *args, **kwargs):
        return iterable

from dictionary import Word, cyrillic
from helpers import strip_stress, strip_suffix_number

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
	candidate_norms = set()

	def add_candidate(value):
		if not value or not isinstance(value, str):
			return
		candidate = value.strip()
		normalized_candidate = _normalize_word(candidate)
		# Preserve the original accented candidate text, but prevent duplicate
		# perfective targets that share the same accentless base. This ensures
		# почека́ти and зачека́ти are kept distinct while still deduping false
		# repeats caused by accentless normalization.
		if candidate and normalized_candidate != canonical_source and normalized_candidate not in candidate_norms:
			candidates.append(candidate)
			candidate_norms.add(normalized_candidate)

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

MISSING_FORMS_CACHE_FILE = os.path.join(DATA_DIR, 'lcorp_missing_forms_cache.json')
L_CORP_ERROR_LOG_FILE = os.path.join(DATA_DIR, 'lcorp_missing_forms_errors.json')

# Caches are deprecated in offline mode
wiktionary_cache = {}
inflection_cache = {}

# LCoRP error tracking
_lcorp_error_log = []

# Lazy-loaded offline database
_wiktionary_database = None
_wiktionary_index = None


def load_missing_forms_cache():
    try:
        with open(MISSING_FORMS_CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_missing_forms_cache(cache):
    try:
        with open(MISSING_FORMS_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def save_lcorp_error_log():
    try:
        categories = defaultdict(int)
        for entry in _lcorp_error_log:
            categories[entry.get('category') or 'unknown'] += 1
        snapshot = {
            'summary': {
                'total_failures': len(_lcorp_error_log),
                'categories': dict(categories),
            },
            'errors': list(_lcorp_error_log),
        }
        with open(L_CORP_ERROR_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _record_lcorp_error(word, category, message, request_type=None, status_code=None, url=None, details=None):
    entry = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'word': word,
        'category': category,
        'message': message,
        'request_type': request_type,
        'status_code': status_code,
        'url': url,
        'details': details,
    }
    _lcorp_error_log.append(entry)


def get_lcorp_error_summary():
    categories = defaultdict(int)
    for entry in _lcorp_error_log:
        categories[entry.get('category') or 'unknown'] += 1
    return {
        'total_failures': len(_lcorp_error_log),
        'categories': dict(categories),
    }


def has_lcorp_errors():
    return get_lcorp_error_summary()['total_failures'] > 0


def print_lcorp_error_summary():
    summary = get_lcorp_error_summary()
    if summary['total_failures'] == 0:
        return
    print('LCoRP missing forms error summary:')
    print(f"  Total failures: {summary['total_failures']}")
    for category, count in sorted(summary['categories'].items()):
        print(f"  {category}: {count}")
    print(f"  Details file: {L_CORP_ERROR_LOG_FILE}")

_LCORP_URL = 'https://lcorp.ulif.org.ua/dictua/dictua.aspx'
_LCORP_INDECLINABLE_TEXT = 'незмінювана словникова одиниця'
_lcorp_thread_local = threading.local()


def _lcorp_fetch_page(url, data=None, headers=None, timeout=30):
    headers = headers or {}
    headers.setdefault('User-Agent', 'Mozilla/5.0 (compatible; UkrainianETL/1.0)')
    request_type = 'GET' if data is None else 'POST'
    try:
        session = getattr(_lcorp_thread_local, 'session', None)
        if session is None:
            session = requests.Session()
            _lcorp_thread_local.session = session
        if data is None:
            response = session.get(url, headers=headers, timeout=timeout)
        else:
            response = session.post(url, data=data, headers=headers, timeout=timeout)
        response.encoding = response.encoding or 'utf-8'
        response.raise_for_status()
        return response.text
    except requests.exceptions.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        category = 'rate limited' if status_code == 429 else 'server failure' if status_code and 500 <= status_code < 600 else 'network failure'
        _record_lcorp_error(
            word=None,
            category=category,
            message=str(exc),
            request_type=request_type,
            status_code=status_code,
            url=url,
            details={'headers': headers, 'timeout': timeout},
        )
        raise
    except requests.exceptions.RequestException as exc:
        _record_lcorp_error(
            word=None,
            category='network failure',
            message=str(exc),
            request_type=request_type,
            status_code=getattr(exc.response, 'status_code', None) if hasattr(exc, 'response') else None,
            url=url,
            details={'headers': headers, 'timeout': timeout},
        )
        raise


def _lcorp_extract_hidden_input(html, name):
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find('input', {'id': name})
    return element['value'] if element and element.has_attr('value') else ''

def _lcorp_get_state():
    state = getattr(_lcorp_thread_local, 'state', None)
    if state is not None:
        return state
    html = _lcorp_fetch_page(_LCORP_URL)
    state = {
        'viewstate': _lcorp_extract_hidden_input(html, '__VIEWSTATE'),
        'viewstategenerator': _lcorp_extract_hidden_input(html, '__VIEWSTATEGENERATOR'),
        'eventvalidation': _lcorp_extract_hidden_input(html, '__EVENTVALIDATION'),
    }
    _lcorp_thread_local.state = state
    return state


def _extract_lcorp_tag_text(html, class_name):
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.find(class_=class_name)
    if element is None:
        return None
    texts = [s for s in element.find_all(string=True, recursive=False)]
    return ''.join(texts).strip()


def _extract_lcorp_article(html):
    soup = BeautifulSoup(html, 'html.parser')
    article_td = soup.find('td', {'id': 'ContentPlaceHolder1_article'})
    return str(article_td) if article_td else ''


def _parse_lcorp_rows(article_html):
    soup = BeautifulSoup(article_html, 'html.parser')
    rows = []
    for tr in soup.find_all('tr'):
        cells = [td.get_text(strip=True) for td in tr.find_all('td')]
        if cells:
            rows.append(cells)
    return rows


def _parse_lcorp_word_info(text):
    text = text or ''
    tags = [x.strip() for x in re.split(r'[,;\s]+', text) if x.strip()]
    grammar = {
        'gender': None,
        'animacy': None,
        'aspect': None,
    }
    for tag in tags:
        if tag in ('чоловічий', 'чоловічого', 'чол.'): 
            grammar['gender'] = 'male'
        elif tag in ('жіночий', 'жіночого', 'жін.'): 
            grammar['gender'] = 'female'
        elif tag in ('середній', 'середнього', 'с.'): 
            grammar['gender'] = 'neuter'
        elif tag in ('неодушевлений', 'неодушевленого'): 
            grammar['animacy'] = 'inanimate'
        elif tag in ('одушевлений', 'одушевленого'): 
            grammar['animacy'] = 'animate'
        elif tag in ('доконаного', 'доконаний'): 
            grammar['aspect'] = 'perfective'
        elif tag in ('недоконаного', 'недоконаний'): 
            grammar['aspect'] = 'imperfective'
    return grammar


def _clean_lcorp_result(result, word_str):
    """Strip LCoRP prefix material (e.g. prepositions before locative) by
    keeping only the rightmost N words of each form, where N is the number
    of words in the search term.  Passes through None entries unchanged."""
    if result[0] is None:
        return result
    found_word, word_info, forms, form_type = result
    word_len = len(word_str.split())
    cleaned_forms = {}
    for k, v in (forms or {}).items():
        cleaned_forms[k] = [' '.join(f.split()[-word_len:]) for f in v]
    cleaned_found = ' '.join(found_word.split()[:word_len]) if found_word else found_word
    return (cleaned_found, word_info, cleaned_forms, form_type)


def _parse_lcorp_inflection_results(word, article_html):
    found_word = _extract_lcorp_tag_text(article_html, 'word_style')
    word_info = _extract_lcorp_tag_text(article_html, 'gram_style')
    rows = _parse_lcorp_rows(article_html)

    form_type = None
    forms = None
    indeclinable = _LCORP_INDECLINABLE_TEXT in article_html
    if rows:
        if rows[0][0] == 'Інфінітив':
            form_type = 'verb'
            forms = _parse_lcorp_verb_rows(rows)
        elif len(rows) > 1 and rows[1][0] == 'називний':
            form_type = 'noun'
            forms = _parse_lcorp_noun_rows(rows)
        elif len(rows) > 1 and rows[1][0] == 'чол. р.':
            form_type = 'adj'
            forms = _parse_lcorp_adjective_rows(rows)
        elif rows[0] and rows[0][0] == 'Я':
            word_str = word if isinstance(word, str) else word.word
            forms = _parse_lcorp_pronoun(word_str)
    if forms is None:
        forms = {}
    if indeclinable:
        form_type = 'indeclinable'
    return [(found_word, _parse_lcorp_word_info(word_info), forms, form_type)]


def _parse_lcorp_verb_rows(rows):
    forms = {}
    last_seen_type = None
    current_tense = None
    for row in rows:
        if row[0] == 'Інфінітив':
            if len(row) > 1:
                forms['inf'] = [row[1]]
        if 'Наказовий' in row[0]:
            current_tense = 'imp'
        if 'МАЙБУТНІЙ' in row[0]:
            current_tense = 'fut'
        if 'ТЕПЕРІШНІЙ' in row[0]:
            current_tense = 'pres'
        if 'МИНУЛИЙ' in row[0]:
            current_tense = 'past'
        if row[0] == '1 особа':
            if current_tense == 'imp':
                if len(row) > 2:
                    forms['imp 1p'] = [row[2]]
            else:
                if len(row) > 1:
                    forms[f'{current_tense} 1s'] = [row[1]]
                if len(row) > 2:
                    forms[f'{current_tense} 1p'] = [row[2]]
        if row[0] == '2 особа':
            if len(row) > 1:
                forms[f'{current_tense} 2s'] = [row[1]]
            if len(row) > 2:
                forms[f'{current_tense} 2p'] = [row[2]]
        if row[0] == '3 особа':
            if len(row) > 1:
                forms[f'{current_tense} 3s'] = [row[1]]
            if len(row) > 2:
                forms[f'{current_tense} 3p'] = [row[2]]
        if 'чол.' in row[0]:
            if len(row) > 1:
                forms['past ms'] = [row[1]]
            if len(row) > 2:
                forms['past p'] = [row[2]]
        if 'жін.' in row[0] and len(row) > 1:
            forms['past fs'] = [row[1]]
        if 'сер.' in row[0] and len(row) > 1:
            forms['past ns'] = [row[1]]
        if row[0] in ('Активний дієприкметник', 'Пасивний дієприкметник', 'Дієприслівник', 'Безособова форма'):
            last_seen_type = row[0]
        elif last_seen_type is not None:
            form_type = {
                'Активний дієприкметник': 'act pp',
                'Пасивний дієприкметник': 'pas pp',
                'Дієприслівник': 'adv pp',
                'Безособова форма': 'imp pp',
            }.get(last_seen_type)
            if form_type and len(row) > 0:
                forms[form_type] = [row[0]]
    for form_id in list(forms.keys()):
        if forms[form_id] == '':
            del forms[form_id]
    return forms


def _parse_lcorp_noun_rows(rows):
    forms = {}
    for row in rows:
        case = None
        if row[0] == 'називний':
            case = 'nom'
        if row[0] == 'родовий':
            case = 'gen'
        if row[0] == 'давальний':
            case = 'dat'
        if row[0] == 'знахідний':
            case = 'acc'
        if row[0] == 'орудний':
            case = 'ins'
        if row[0] == 'місцевий':
            case = 'loc'
        if row[0] == 'кличний':
            case = 'voc'
        if case is not None:
            if len(row) > 2:
                forms[f'{case} ns'] = [row[1]]
                forms[f'{case} np'] = [row[2]]
            elif len(row) > 1:
                forms[f'{case} n'] = [row[1]]
    return forms


def _parse_lcorp_adjective_rows(rows):
    forms = {}
    for row in rows:
        case = None
        if row[0] == 'називний':
            case = 'nom'
        if row[0] == 'родовий':
            case = 'gen'
        if row[0] == 'давальний':
            case = 'dat'
        if row[0] == 'знахідний':
            case = 'acc'
        if row[0] == 'орудний':
            case = 'ins'
        if row[0] == 'місцевий':
            case = 'loc'
        if case is not None and len(row) > 1:
            forms[f'{case} am'] = [row[1]]
            if len(row) > 2:
                forms[f'{case} an'] = [row[2]]
    return forms


def _parse_lcorp_pronoun(word):
    nom = ['я', 'ти', 'він', 'воно́', 'вона́', 'ми', 'ви', 'вони́']
    gen = ['мене́', 'тебе́', 'його́, ньо́го', 'його́, ньо́го', 'її́, не́ї', 'нас', 'вас', 'їх, них*']
    dat = ['мені́', 'тобі́', 'йому́', 'йому́', 'їй', 'нам', 'вам', 'їм']
    acc = ['мене́', 'тебе́', 'його́, ньо́го', 'його́, ньо́го', 'її́, не́ї', 'нас', 'вас', 'їх, них*']
    ins = ['мно́ю', 'тобо́ю', 'ним', 'ним', 'не́ю', 'на́ми', 'ва́ми', 'ни́ми']
    loc = ['мені́', 'тобі́', 'ньо́му, нім', 'ньо́му, нім', 'ній', 'нас', 'вас', 'них']
    index = {e.replace('́', ''): i for i, e in enumerate(nom)}
    word = word.replace('́', '')
    if word not in index:
        return None
    forms = defaultdict(lambda: [])
    forms['nom n'] += nom[index[word]].split(', ')
    forms['gen n'] += gen[index[word]].split(', ')
    forms['dat n'] += dat[index[word]].split(', ')
    forms['acc n'] += acc[index[word]].split(', ')
    forms['ins n'] += ins[index[word]].split(', ')
    forms['loc n'] += loc[index[word]].split(', ')
    return dict(forms)


def _lcorp_search_candidates(word):
    try:
        state = _lcorp_get_state()
    except Exception as exc:
        _record_lcorp_error(
            word=word,
            category='parsing failure',
            message=f'failed to retrieve or parse LCoRP state: {exc}',
            request_type='GET',
            url=_LCORP_URL,
        )
        return [[None, None, None, None]]

    data = {
        'ctl00$ContentPlaceHolder1$ScriptManager1': 'ctl00$ContentPlaceHolder1$UpdText|ctl00$ContentPlaceHolder1$search',
        '__EVENTTARGET': '',
        '__EVENTARGUMENT': '',
        '__VIEWSTATE': state['viewstate'],
        '__VIEWSTATEGENERATOR': state['viewstategenerator'],
        '__EVENTVALIDATION': state['eventvalidation'],
        'ctl00$ContentPlaceHolder1$tsearch': word,
        'ctl00$ContentPlaceHolder1$search.x': '0',
        'ctl00$ContentPlaceHolder1$search.y': '0',
    }
    try:
        html = _lcorp_fetch_page(_LCORP_URL, data=data, headers={
            'Origin': 'https://lcorp.ulif.org.ua',
            'Referer': _LCORP_URL,
        })
    except requests.exceptions.RequestException:
        return [[None, None, None, None]]

    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table', {'id': 'DictMainTab'})
    if not table:
        _record_lcorp_error(
            word=word,
            category='word not found',
            message='no candidate search results table found',
            request_type='POST',
            url=_LCORP_URL,
        )
        return [[None, None, None, None]]
    anchor_texts = [a.get_text(strip=True) for a in table.find_all('a')]
    normalized_target = strip_stress(word)
    all_results = []
    for index, anchor in enumerate(anchor_texts):
        anchor_base = strip_suffix_number(anchor)
        if strip_stress(anchor_base) == normalized_target:
            results = _lcorp_fetch_candidate_results(word, index, state)
            if not results:
                continue
            found_word = results[0][0]
            if found_word:
                found_base = strip_suffix_number(found_word)
                if strip_stress(found_base) == normalized_target:
                    for r in results:
                        if r[0]:
                            r = list(r)
                            r[0] = strip_suffix_number(r[0])
                            all_results.append(tuple(r))
                        else:
                            all_results.append(r)

    if all_results:
        return all_results

    _record_lcorp_error(
        word=word,
        category='word not found',
        message='target word not found in LCoRP search results',
        request_type='POST',
        url=_LCORP_URL,
        details={'anchors': anchor_texts[:20]},
    )
    return [[None, None, None, None]]


def _lcorp_fetch_candidate_results(word, index, state):
    data = {
        'ctl00$ContentPlaceHolder1$ScriptManager1': 'ctl00$ContentPlaceHolder1$UpdText|ctl00$ContentPlaceHolder1$dgv',
        '__EVENTTARGET': 'ctl00$ContentPlaceHolder1$dgv',
        '__EVENTARGUMENT': f'Select${index}',
        '__VIEWSTATE': state['viewstate'],
        '__VIEWSTATEGENERATOR': state['viewstategenerator'],
        '__EVENTVALIDATION': state['eventvalidation'],
        'ctl00$ContentPlaceHolder1$tsearch': word,
    }
    try:
        html = _lcorp_fetch_page(_LCORP_URL, data=data, headers={
            'Origin': 'https://lcorp.ulif.org.ua',
            'Referer': _LCORP_URL,
        })
    except requests.exceptions.RequestException:
        return [[None, None, None, None]]

    article = _extract_lcorp_article(html)
    if not article:
        _record_lcorp_error(
            word=word,
            category='parsing failure',
            message='could not extract article HTML from candidate page',
            request_type='POST',
            url=_LCORP_URL,
        )
        return [[None, None, None, None]]
    return _parse_lcorp_inflection_results(word, article)


def _fetch_lcorp_inflection(word):
    try:
        return _lcorp_search_candidates(word.word)
    except Exception as exc:
        _record_lcorp_error(
            word=word.word if getattr(word, 'word', None) else None,
            category='unexpected failure',
            message=f'exception fetching LCoRP inflection: {exc}',
            request_type='LCoRP lookup',
            url=_LCORP_URL,
        )
        return None


def _base_lookup_missing_forms(word, cache=None, pos=None):
    """Fetch or retrieve from cache, storing results as close to the webpage
    as possible (with any LCoRP prefix material still present)."""
    key = strip_stress(word.word)
    if pos:
        key = f"{key}\x00{pos}"

    if cache is None:
        cache = {}

    if key in cache:
        return cache[key]

    results = _fetch_lcorp_inflection(word)
    if results and not all(r[0] is None for r in results):
        if pos:
            # LCoRP has no dedicated pronoun inflection parser; pronoun tables
            # (including reflexive pronouns like себе́) use the noun table format
            # and return form_type='noun'. Accept that for pronoun lookups.
            results = [r for r in results if r[3] == pos or r[3] == 'indeclinable' or (pos == 'pronoun' and r[3] == 'noun')]
        if results:
            cache[key] = results
            return results

    results = [[None, None, None, None]]
    cache[key] = results
    return results


def lookup_missing_forms(word, cache=None, pos=None):
    """Like _base_lookup_missing_forms but strips LCoRP prefix material
    (e.g. prepositions before locative forms) from every result before
    returning."""
    results = _base_lookup_missing_forms(word, cache=cache, pos=pos)
    return [_clean_lcorp_result(r, word.word) for r in results]


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
		if any(tag in tags for tag in ('canonical', 'initialism', 'abbreviation', 'variant', 'diminutive', 'augmentative', 'contraction')):
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
			if source in ('declension', 'conjugation', 'inflection') and 'tags' in f:
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
	sounds = []
	for s in entry.get('sounds', []):
		sound_entry = {}
		if s.get('ipa'):
			sound_entry['ipa'] = s['ipa']
		if s.get('mp3_url'):
			sound_entry['mp3_url'] = s['mp3_url']
		elif s.get('ogg_url'):
			sound_entry['ogg_url'] = s['ogg_url']
		if sound_entry:
			sounds.append(sound_entry)

	parsed_entries = []
	has_indeclinable_sense = any(
		'indeclinable' in (s.get('tags') or [])
		for s in entry.get('senses', [])
	)
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
			else:
				# The word isn't a personal pronoun form (e.g. reflexive pronoun себе́).
				# Kaikki stores the full personal-pronoun declension table under these
				# entries, but reflexive pronouns don't have person distinctions.
				# Drop all person-specific forms, leaving only general case forms
				# (usually just the reflexive forms like себе́, собі́, собо́ю).
				# If none survive, forms_status='missing' triggers a LCoRP lookup,
				# which returns the correct reflexive paradigm.
				filtered_forms = {}
				person_vals = {fv for pairs in pronoun_form_persons.values() for fv, pk in pairs}
				for form_key, form_values in entry_forms.items():
					non_person_vals = [fv for fv in form_values if fv not in person_vals]
					if non_person_vals:
						filtered_forms[form_key] = non_person_vals
				entry_forms = filtered_forms if filtered_forms else None

		entry_sounds = sounds if strip_stress(ws) == strip_stress(word_spelling) else None
		parsed_entries.append({
			'word': ws,
			'pos': ws_pos,
			'variants': variants or None,
			'definitions': definitions,
			'synonyms': entry_synonyms or None,
			'sounds': entry_sounds or None,
			'forms': entry_forms,
			'form_type': form_type,
			'info': word_info if any(word_info.values()) else None,
			'aspect_candidates': aspect_candidates,
			'forms_status': 'available' if entry_forms else ('indeclinable' if has_indeclinable_sense else 'missing'),
			'forms_source': 'wiktionary' if entry_forms else None,
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


def _extract_translation_definitions(translation, sense=None):
	if not isinstance(translation, dict):
		return None
	if isinstance(sense, dict):
		for gloss_field in ('raw_glosses', 'glosses'):
			glosses = sense.get(gloss_field)
			if isinstance(glosses, list) and glosses:
				return glosses
	sense = translation.get('sense')
	if isinstance(sense, str) and sense.strip():
		return [sense.strip()]
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
		word = word.strip()
		definitions = _extract_translation_definitions(translation, sense_context)
		if not definitions:
			return
		pos = entry.get('pos', 'particle')
		key = (word, pos, tuple(definitions))
		if key in seen:
			return
		seen.add(key)
		info = _build_grammar_info([t for t in (translation.get('tags') or []) if isinstance(t, str)])
		source_word = entry.get('word') if isinstance(entry.get('word'), str) else None
		parsed_entries.append({
			'word': word,
			'pos': pos,
			'variants': None,
			'definitions': definitions,
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
		for res in tqdm(pool.imap(_parse_chunk_worker, _iter_jsonl_chunks(kaikki_path, chunk_size), chunksize=1),
			desc='parsing wiktionary file', unit='chunk', disable=not os.isatty(1)):
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
	for pe in tqdm(ukrainian_entries, desc='merging ukrainian entries', unit='entry', disable=not os.isatty(1)):
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
			w.add_forms(pos, pe.get('forms') or {}, pe['form_type'], source='wiktionary')
		if pe.get('sounds'):
			w.add_sounds(pos, pe['sounds'])
		if pe.get('forms_status') and pos in w.usages:
			usage = w.usages[pos]
			usage.forms_status = pe['forms_status']
			if pe.get('forms_source'):
				usage.forms_source = pe['forms_source']

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
		if pe.get('forms_status') and pos in w.usages:
			usage = w.usages[pos]
			usage.forms_status = pe['forms_status']
			if pe.get('forms_source'):
				usage.forms_source = pe['forms_source']
		if pe.get('info'):
			w.add_info(pos, pe['info'])

	if return_aspect_candidates:
		return list(words_map.values()), aspect_pairs
	return list(words_map.values())
