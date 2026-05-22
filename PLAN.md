## Plan: Bug fixes and reliability improvements for ETL pipeline

TL;DR: Use the existing local dump files under `etl/sources` to eliminate all remote network calls from the ETL pipeline, while also stabilizing key parser and dictionary merge logic in `etl/extract.py`, `etl/ontolex.py`, and `etl/dictionary.py`.

**Steps**

1. Inventory local source coverage and map remote calls to local files.
   - `en_dbnary_ontolex.ttl` replaces the OntoLex TTL download from `http://kaiko.getalp.org/static/ontolex/latest/en_dbnary_ontolex.ttl.bz2`.
   - `kaikki.org-dictionary-Ukrainian.jsonl` replaces Wiktionary network calls for:
     - lemma category pagination (`Category:Ukrainian_lemmas`)
     - per-word parse API fetches for definitions and forms
   - `publicist_84k_lex_dict_orig.csv` replaces the remote frequency CSV at `http://ukrkniga.org.ua/ukr_rate/publicist_84k_lex_dict_orig.csv`.
   - Determine if local JSONL data can also replace ULIF inflection scraping by using `forms` / `inflection_templates`.

2. Refactor `etl/extract.py` to use local dumps.
   - Remove or lazy-load `get_viewstate()` so import no longer performs remote network access.
   - Add a local dump loader for `etl/sources/kaikki.org-dictionary-Ukrainian.jsonl`.
   - Replace `get_lemmas()` with a lemma list derived from the JSONL dump.
   - Replace `get_wiktionary_word()` with a lookup against the parsed JSONL dump and convert its structured data into `Word` objects.
   - Replace `get_frequency_list()` remote download with a parser that reads `etl/sources/publicist_84k_lex_dict_orig.csv`.
   - If local dump supports it, deprecate `scrape_inflection()` and the ULIF POST workflow; otherwise keep it as a fallback.

3. Refactor `etl/ontolex.py` to use the local TTL source.
   - Point `Ontolex` at `etl/sources/en_dbnary_ontolex.ttl` instead of downloading from `kaiko.getalp.org`.
   - Ensure `Ontolex.__init__()` can still use cache if available, but does not require network.

4. Fix the most important logic bugs found in the existing code.
   - In `extract.get_wiktionary_word()`, do not `return` entirely when a headword has no definition pointer; skip that headword instead.
   - Correct `get_additional_adjectival_forms()` so `prefix += 0` is replaced with string-safe logic and parenthesis text extraction works reliably.
   - Guard `get_inflection()` / `clean_result()` against `None` `word_info` and malformed result rows.
   - Replace bare `except:` blocks in cache loading with explicit exceptions like `FileNotFoundError` and `json.JSONDecodeError`.
   - Fix `Usage.get_forms()` in `etl/dictionary.py` to avoid silently overwriting form entries from different `form_type` objects.
   - Fix `Word.add_frequencies()` so it does not mutate the shared `frequencies` dict while normalizing POS keys.
   - Correct `Dictionary._handle_no_accent()` to preserve distinct homographs like noun/verb `мати` instead of collapsing them prematurely.
   - Fix `Ontolex_Word.get_translations()` so it uses a proper dict structure instead of treating a list like a dict.
   - Harden `Ontolex.parse_ontolex()` parsing to handle TTL syntax more robustly and avoid fragile string-split failures.

5. Add configuration or path defaults for local sources.
   - Use `etl/sources` as the default directory for local dump files.
   - Prefer explicit file paths with sensible fallback to `data/` only if local source is absent.

6. Verify and validate the new flow.
   - Run a controlled ETL pass using the local dumps without any network connectivity.
   - Confirm `etl/main.py` or a smaller test script can build `dictionary_data.json`, `index.json`, and `word_dict.json`.
   - Validate that the set of network calls from `etl/extract.py` and `etl/ontolex.py` is removed or disabled.

**Relevant files**

- `/Users/edmondc/ws/ukrainian/etl/extract.py`
- `/Users/edmondc/ws/ukrainian/etl/ontolex.py`
- `/Users/edmondc/ws/ukrainian/etl/dictionary.py`
- `/Users/edmondc/ws/ukrainian/etl/main.py`
- `/Users/edmondc/ws/ukrainian/etl/sources/en_dbnary_ontolex.ttl`
- `/Users/edmondc/ws/ukrainian/etl/sources/kaikki.org-dictionary-Ukrainian.jsonl`
- `/Users/edmondc/ws/ukrainian/etl/sources/publicist_84k_lex_dict_orig.csv`

**Verification**

1. Confirm the ETL run does not call remote URLs by either disconnecting network or instrumenting HTTP access.
2. Check that `data/ontolex_data.json`, `data/dictionary_data.json`, `data/index.json`, and `data/word_dict.json` can be produced from local source files.
3. Run a small sample lookup for known words like `мати` and verify noun/verb separation is preserved.
4. Ensure no new runtime exceptions occur from the new local loader paths.

**Decisions**

- The local dumps are sufficient to eliminate the network fetches in the current ETL pipeline.
- The implementation should prioritize local file usage first and keep network fetches only as optional fallback.
- Fixing parser/dictionary bugs alongside this change will make the pipeline more stable and less brittle.
