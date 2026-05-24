import argparse
import json
import os
from pathlib import Path
from typing import Optional

def validate_environment(raw_dbnary_path: str, frequency_csv_path: str, kaikki_path: str) -> None:
    missing = [name for name, path in (
        ('RAW_DBNARY_PATH', raw_dbnary_path),
        ('FREQUENCY_CSV_PATH', frequency_csv_path),
        ('KAIKKI_PATH', kaikki_path),
    ) if not Path(path).exists()]

    if missing:
        raise FileNotFoundError(f"Missing required ETL source files: {', '.join(missing)}")


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


def main(debug_words: Optional[list[str]] = None, verbose: bool = False) -> None:
    if Path.cwd().name != 'etl':
        raise RuntimeError('Run this from the etl directory: cd etl')

    source_dir = Path.cwd() / 'sources'
    cache_dir = Path(os.environ.get('DATA_DIR', str(Path.cwd() / 'cache')))
    os.environ['DATA_DIR'] = str(cache_dir)
    os.makedirs(cache_dir, exist_ok=True)

    output_dir = Path(os.environ.get('OUTPUT_DIR', str(Path.cwd() / 'output')))
    os.environ['OUTPUT_DIR'] = str(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    raw_dbnary_path = os.environ.get('RAW_DBNARY_PATH', str(source_dir / 'en_dbnary_ontolex.ttl'))
    frequency_csv_path = os.environ.get('FREQUENCY_CSV_PATH', str(source_dir / 'publicist_84k_lex_dict_orig.csv'))
    kaikki_path = os.environ.get('KAIKKI_PATH', str(source_dir / 'kaikki.org-dictionary-Ukrainian.jsonl'))
    deletion_log_path = os.environ.get('DELETION_LOG_PATH', str(output_dir / 'deletions.json'))

    validate_environment(raw_dbnary_path, frequency_csv_path, kaikki_path)

    from ontolex import Ontolex

    o = Ontolex(use_cache=True, use_raw_cache=True, raw_dbnary_path=raw_dbnary_path)
    d = o.get_dictionary(
        kaikki_path=kaikki_path,
        frequency_csv_path=frequency_csv_path,
        deletion_log_path=deletion_log_path,
    )
    d.add_wiktionary_words()
    d.dump(output_dir / 'dictionary_data.json', indent=4, final_form=True)
    d.make_index(output_dir / 'index.json', output_dir / 'word_dict.json', indent=4)
    d.dump(output_dir / 'words.json', final_form=True)
    d.write_deletion_log()
    report_debug_words(d, debug_words=debug_words, verbose=verbose)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the Ukrainian ETL pipeline')
    parser.add_argument('--debug-words', nargs='+', default=None,
        help='Word(s) to inspect after pipeline completion')
    parser.add_argument('--debug-word', action='append', default=None,
        help='Word to inspect after pipeline completion (repeatable)')
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
    main(debug_words=debug_words, verbose=args.verbose)
