#!/usr/bin/env python3
import argparse
import json
import os
import time
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from dictionary import Word

RETRYABLE_DEFAULT_CATEGORIES = {
    'network failure',
    'rate limited',
    'server failure',
}


def load_json(path):
    if not path.exists():
        return None
    try:
        with path.open('r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        raise RuntimeError(f'Unable to parse JSON from {path}')


def save_json(path, data):
    with path.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_word(word):
    return Word(word).get_word_no_accent()


def is_successful_result(results):
    if not results or not isinstance(results, list):
        return False
    return any(
        isinstance(entry, (list, tuple)) and len(entry) >= 1 and entry[0] is not None
        for entry in results
    )


def build_retry_index(errors, allowed_categories, retry_all=False):
    grouped = defaultdict(list)
    for entry in errors:
        word = entry.get('word')
        if not word:
            continue
        category = entry.get('category')
        if retry_all or category in allowed_categories:
            grouped[normalize_word(word)].append(entry)
    return grouped


def main():
    parser = argparse.ArgumentParser(description='Retry failed LCoRP missing-form lookups and update the cache file.')
    parser.add_argument('--data-dir', default=os.environ.get('DATA_DIR', 'cache'),
        help='Cache directory to use (default from DATA_DIR or cache)')
    parser.add_argument('--max-attempts', type=int, default=3,
        help='Maximum retry attempts per word')
    parser.add_argument('--delay', type=float, default=2.0,
        help='Base delay between retry attempts in seconds')
    parser.add_argument('--all', action='store_true', dest='retry_all',
        help='Retry all logged failures regardless of category')
    parser.add_argument('--categories', nargs='+', default=None,
        help='List of error categories to retry (overrides default categories)')
    args = parser.parse_args()

    os.environ['DATA_DIR'] = args.data_dir
    cache_dir = Path(args.data_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    import extract

    error_file = Path(extract.L_CORP_ERROR_LOG_FILE)
    cache_file = Path(extract.MISSING_FORMS_CACHE_FILE)

    raw = load_json(error_file)
    if raw is None:
        print(f'No error log found at {error_file}. Nothing to retry.')
        return

    errors = raw.get('errors') if isinstance(raw, dict) and 'errors' in raw else raw
    if not isinstance(errors, list):
        raise RuntimeError(f'Invalid error log shape in {error_file}')

    cache = extract._load_missing_forms_cache()
    cache_keys = set(cache.keys()) if isinstance(cache, dict) else set()

    categories = set(args.categories) if args.categories else RETRYABLE_DEFAULT_CATEGORIES
    retryable = build_retry_index(errors, categories, retry_all=args.retry_all)
    retryable = {
        word_key: entries
        for word_key, entries in retryable.items()
        if word_key not in cache_keys
    }
    if not retryable:
        print('No retryable failures found in error log (all words are already cached or not retryable).')
        # Remove any logged failures for cached words from the error log
        remaining_errors = [entry for entry in errors if normalize_word(entry.get('word', '')) not in cache_keys]
        save_json(error_file, {
            'summary': {
                'total_failures': len(remaining_errors),
                'categories': {k: sum(1 for e in remaining_errors if e.get('category') == k) for k in {e.get('category') or 'unknown' for e in remaining_errors}},
            },
            'errors': remaining_errors,
        })
        print(f'  cleaned cached words from {error_file}')
        return

    success_words = set()
    retry_results = []

    print(f'Retrying {len(retryable)} word(s) from {error_file}')
    for word_key, entries in retryable.items():
        original_words = sorted({entry['word'] for entry in entries if entry.get('word')})
        word_text = original_words[0]
        word_obj = Word(word_text)

        print(f'  Retrying: {word_text} (normalized: {word_key})')
        attempt = 0
        success = False
        last_error = None

        while attempt < args.max_attempts and not success:
            attempt += 1
            try:
                results = extract.lookup_missing_forms(word_obj, use_cache=False)
            except Exception as exc:
                last_error = str(exc)
                print(f'    attempt {attempt}/{args.max_attempts} failed: {exc}')
            else:
                if is_successful_result(results):
                    cache[word_key] = results
                    extract._save_missing_forms_cache(cache)
                    print(f'    success on attempt {attempt}')
                    success = True
                    success_words.add(word_key)
                else:
                    last_error = 'no valid inflection results returned'
                    print(f'    attempt {attempt}/{args.max_attempts} did not return valid results')

            if not success and attempt < args.max_attempts:
                backoff = args.delay * attempt
                time.sleep(backoff)

        for entry in entries:
            retry_results.append((word_key, success, last_error, entry))

    remaining_errors = []
    for entry in errors:
        word = entry.get('word')
        if not word:
            remaining_errors.append(entry)
            continue
        if normalize_word(word) in success_words:
            continue
        if not args.retry_all and entry.get('category') not in categories:
            remaining_errors.append(entry)
            continue

        entry = dict(entry)
        entry['retry_attempts'] = entry.get('retry_attempts', 0) + 1
        entry['last_retry'] = datetime.utcnow().isoformat() + 'Z'
        if not entry.get('last_message') and entry.get('word') and normalize_word(entry['word']) in {r[0] for r in retry_results if not r[1]}:
            # Only keep the last error message for failed retry attempts
            entry['last_message'] = next((r[2] for r in retry_results if r[0] == normalize_word(entry['word']) and not r[1]), None)
        remaining_errors.append(entry)

    snapshot = {
        'summary': {
            'total_failures': len(remaining_errors),
            'categories': defaultdict(int),
        },
        'errors': remaining_errors,
    }
    for entry in remaining_errors:
        category = entry.get('category') or 'unknown'
        snapshot['summary']['categories'][category] += 1

    save_json(error_file, snapshot)

    print('Retry pass complete.')
    print(f'  succeeded: {len(success_words)}')
    print(f'  remaining failures: {len(remaining_errors)}')
    print(f'  updated cache: {cache_file}')
    print(f'  updated errors: {error_file}')


if __name__ == '__main__':
    main()
