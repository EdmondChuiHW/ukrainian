import argparse
import json
import os
from pathlib import Path
from typing import Optional

def validate_environment(frequency_csv_path: str, kaikki_path: str) -> None:
    missing = [name for name, path in (
        ('FREQUENCY_CSV_PATH', frequency_csv_path),
        ('KAIKKI_PATH', kaikki_path),
    ) if not Path(path).exists()]

    if missing:
        raise FileNotFoundError(f"Missing required ETL source files: {', '.join(missing)}. You may need to run `update_sources.py`.")
    
    print (f"Environment validated. Using\nFREQUENCY_CSV_PATH={frequency_csv_path}\nKAIKKI_PATH={kaikki_path}")


def report_debug_words(dictionary, debug_words: Optional[list[str]] = None, verbose: bool = False) -> None:
    if not debug_words:
        return

    debug_info = dictionary.get_debug_info(debug_words)
    print('\nDEBUG WORD REPORT')
    print(f"Final dictionary shape: {debug_info['word_count']} words, {debug_info['final_form_count']} final form entries")

    for query_info in debug_info['queries']:
        query = query_info['query']
        print(f"\nQuery: {query!r}")
        if query_info['candidates']:
            print(f"  Candidates: {len(query_info['candidates'])}")
            for candidate in query_info['candidates']:
                word = candidate['word']
                usages = candidate['usages']
                print(f"  Candidate: '{word}' ({len(usages)} part(s) of speech)")
                for pos, usage in usages.items():
                    defs = usage.get('defs', [])
                    freq = usage.get('freq')
                    info = usage.get('info')
                    forms = usage.get('forms', {})
                    print(f"    - {pos}: {len(defs)} definition(s), freq={freq}, info={info!r}, forms={len(forms)}")
                    if verbose:
                        print(json.dumps(usage, indent=2, ensure_ascii=False))
        else:
            print(f"  No final dictionary entry found for {query!r}.")
        deletions = query_info.get('deletions', [])
        if deletions:
            print(f"  Deletions ({len(deletions)}):")
            for deletion in deletions:
                word = deletion.get('word')
                pos = deletion.get('pos')
                reason = deletion.get('reason')
                typ = deletion.get('type')
                print(f"    - word={word!r} pos={pos!r} type={typ!r} reason={reason!r}")
                if verbose:
                    print(f"      word_obj={deletion.get('word_obj')}")
        else:
            print("  No deletions")


def main(debug_words: Optional[list[str]] = None, verbose: bool = False, fetch_missing_forms: bool = True) -> None:
    if Path.cwd().name != 'etl':
        raise RuntimeError('Run this from the etl directory: cd etl')

    source_dir = Path.cwd() / 'sources'
    cache_dir = Path(os.environ.get('DATA_DIR', str(Path.cwd() / 'cache')))
    os.environ['DATA_DIR'] = str(cache_dir)
    os.makedirs(cache_dir, exist_ok=True)

    output_dir = Path(os.environ.get('OUTPUT_DIR', str(Path.cwd() / 'output')))
    os.environ['OUTPUT_DIR'] = str(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    frequency_csv_path = os.environ.get('FREQUENCY_CSV_PATH', str(source_dir / 'publicist_84k_lex_dict_orig.csv'))
    kaikki_path = os.environ.get('KAIKKI_PATH', str(source_dir / 'downloaded' / 'kaikki.org-dictionary-combined.jsonl'))
    deletion_log_path = os.environ.get('DELETION_LOG_PATH', str(output_dir / 'deletions.json'))

    validate_environment(frequency_csv_path, kaikki_path)

    from dictionary import Dictionary

    d = Dictionary(
        kaikki_path=kaikki_path,
        frequency_csv_path=frequency_csv_path,
        deletion_log_path=deletion_log_path,
    )
    d.add_wiktionary_words(fetch_missing_forms=fetch_missing_forms)
    d.add_verb_aspect_counterparts(
        known_pairs_path=source_dir / 'verb_aspect_known_pairs.json',
    )

    d.dump(output_dir / 'dictionary_data.json', indent=4, final_form=True)
    d.make_index(output_dir / 'index.json', output_dir / 'word_dict.json', indent=4)
    final_data = d.dump(output_dir / 'words.json', final_form=True)
    print(f"{len(final_data)} entries written to {output_dir / 'dictionary_data.json'}")
    d.write_deletion_log()
    report_debug_words(d, debug_words=debug_words, verbose=verbose)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the Ukrainian ETL pipeline')
    parser.add_argument('--debug-words', nargs='+', default=None,
        help='Word(s) to inspect after pipeline completion')
    parser.add_argument('--debug-word', action='append', default=None,
        help='Word to inspect after pipeline completion (repeatable)')
    parser.add_argument('--fetch-missing-forms', action='store_true', default=True,
        help='Enable lookup of missing forms using cached missing-form data')
    parser.add_argument('--no-fetch-missing-forms', action='store_false', dest='fetch_missing_forms',
        help='Disable lookup of missing forms')
    parser.add_argument('--verbose', action='store_true',
        help='Enable verbose debug reporting')
    args = parser.parse_args()
    debug_words = []
    if args.debug_words:
        debug_words.extend(args.debug_words)
    if args.debug_word:
        debug_words.extend(args.debug_word)
    if not debug_words:
        debug_words = None
    main(debug_words=debug_words, verbose=args.verbose, fetch_missing_forms=args.fetch_missing_forms)
