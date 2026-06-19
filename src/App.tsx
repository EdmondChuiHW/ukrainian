import React, { useState, useEffect } from 'react';
import { useQueryState } from 'nuqs';
import SearchBar from './components/SearchBar';
import EntryRow from './components/EntryRow';
import { normalizeText } from './components/utils';
import type { DictionaryEntry, RawDictionaryEntry } from './types/words';
import type { TypeOfUnion } from './types/utils';

const RESULTS_PER_PAGE = 5;

const fetchWords = async () => {
  const wordsRes = await fetch('./words.json');

  if (!wordsRes.ok) {
    throw new Error('Failed to load dictionary data file');
  }

  const rawWords = (await wordsRes.json()) as RawDictionaryEntry[];
  const index = rawWords.map((entry, idx) => buildIndex(entry, idx));
  linkIndex(index);
  return index;
};

const fetchPromise = fetchWords();

const baseExactMatchScore = (entry: DictionaryEntry, query: string): number => {
  if (!query) {
    return 0;
  }
  if (entry.normalizedWord === query) {
    return 6;
  }
  if (entry.normalizedFormTokens.includes(query)) {
    return 5;
  }
  if (
    entry.normalizedWord.startsWith(`${query} `) ||
    entry.normalizedWord.endsWith(` ${query}`) ||
    entry.normalizedWord.includes(` ${query} `)
  ) {
    return 4;
  }
  if (
    entry.normalizedDefs.includes(query) ||
    entry.normalizedForms.includes(query)
  ) {
    return 3;
  }

  if (
    entry.normalizedSynonyms.includes(query) ||
    entry.normalizedDefSynonyms.includes(query) ||
    entry.normalizedCounterparts.includes(query)
  ) {
    return 2;
  }
  if (entry.normalizedWord.includes(query)) {
    return 1;
  }
  return 0;
};

const exactMatchScore = (entry: DictionaryEntry, query: string): number => {
  const score = baseExactMatchScore(entry, query);
  return entry.reverse_translation ? score - 1 : score;
};

const extractTextArray = (value: unknown): string[] => {
  return extractArrayOfTypes(value, ['string']);
};

const extractTextOrNumberArray = (value: unknown): Array<string | number> => {
  return extractArrayOfTypes(value, ['string', 'number']);
};

const extractArrayOfTypes = <T extends TypeOfUnion>(
  value: unknown,
  types: Array<TypeOfUnion>,
): T[] => {
  if (types.includes(typeof value)) return [value as T];
  if (Array.isArray(value))
    return value.flatMap((val) => extractArrayOfTypes(val, types));
  if (value && typeof value === 'object')
    return Object.values(value).flatMap((val) =>
      extractArrayOfTypes(val, types),
    );
  return [];
};

const buildIndex = (
  entry: RawDictionaryEntry,
  index: number,
): DictionaryEntry => {
  const formTokens = extractTextArray(entry.forms)
    .map((val) => normalizeText(val))
    .filter(Boolean);
  const variantTokens = extractTextArray(entry.variants)
    .map((val) => normalizeText(val))
    .filter(Boolean);
  const normalizedFormTokens = [...formTokens, ...variantTokens];
  const normalizedForms = normalizedFormTokens.join(' ');
  return {
    ...entry,
    index,
    normalizedWord: normalizeText(entry.word),
    normalizedDefs: normalizeText(entry.defs?.join(' ') ?? ''),
    normalizedForms,
    normalizedFormTokens,
    normalizedSynonyms: '', // to be filled in linkIndex
    normalizedDefSynonyms: '', // to be filled in linkIndex
    normalizedCounterparts: '', // to be filled in linkIndex
  };
};

const linkIndex = (index: DictionaryEntry[]): void => {
  for (const entry of index) {
    if (!entry.normalizedSynonyms) {
      const synonymTokens = extractTextOrNumberArray(entry.synonyms)
        .map(resolveLink)
        .filter(Boolean);
      entry.normalizedSynonyms = synonymTokens.join(' ');
    }

    if (!entry.normalizedDefSynonyms) {
      const defSynonymTokens = (entry.def_synonyms ?? [])
        .flatMap(extractTextOrNumberArray)
        .map(resolveLink)
        .filter(Boolean);

      entry.normalizedDefSynonyms = defSynonymTokens.join(' ');
    }

    if (!entry.normalizedCounterparts) {
      const counterpartTokens = extractTextOrNumberArray(entry.counterparts)
        .map(resolveLink)
        .filter(Boolean);
      entry.normalizedCounterparts = counterpartTokens.join(' ');
    }
  }

  function resolveLink(val: number | string) {
    return typeof val === 'number'
      ? index[val]?.normalizedWord
      : normalizeText(val);
  }
};

export const App: React.FC = () => {
  const [q, setQuery] = useQueryState('q', {
    defaultValue: '',
    scroll: true,
    history: 'push',
  });
  // keep the normalized query out of search bar so the UI doesn't jump around
  const normalizedQuery = normalizeText(q);

  const [words, setWords] = useState<DictionaryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);

  // Fetch data on mount
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);

        const indexedWords = await fetchPromise;

        setLoading(false);
        setWords(indexedWords);
        setError(null);
      } catch (err: unknown) {
        setLoading(false);
        console.error(err);
        const errorMessage = err instanceof Error ? err.message : String(err);
        setError(errorMessage);
      }
    };

    loadData().catch(
      (e: unknown) => void setError(e instanceof Error ? e.message : String(e)),
    );
  }, []);

  useEffect(() => {
    const onMessage = (ev: MessageEvent<{ q: string } | undefined>): void => {
      if (!ev.data?.q) return;
      if (ev.source !== window.opener) return;

      void setQuery(ev.data.q);
    };
    window.addEventListener('message', onMessage);

    return () => void window.removeEventListener('message', onMessage);
  }, [setQuery]);

  const sortedWords = !normalizedQuery
    ? words
    : words
        .filter(
          (entry) =>
            entry.normalizedWord.includes(normalizedQuery) ||
            entry.normalizedDefs.includes(normalizedQuery) ||
            entry.normalizedSynonyms.includes(normalizedQuery) ||
            entry.normalizedDefSynonyms.includes(normalizedQuery) ||
            entry.normalizedForms.includes(normalizedQuery),
        )
        // sort in place is fine
        .sort((a, b) => {
          const scoreA = exactMatchScore(a, normalizedQuery);
          const scoreB = exactMatchScore(b, normalizedQuery);
          if (scoreB !== scoreA) return scoreB - scoreA;
          return a.index - b.index;
        });

  const fallbackResult =
    sortedWords.length > 0 || !normalizedQuery
      ? null
      : (() => {
          let candidate = normalizedQuery;
          while (candidate) {
            candidate = candidate.slice(0, -1).trim();
            if (!candidate) break;

            const matches = words.filter(
              (entry) =>
                entry.normalizedWord.includes(candidate) ||
                entry.normalizedDefs.includes(candidate) ||
                entry.normalizedSynonyms.includes(candidate) ||
                entry.normalizedDefSynonyms.includes(candidate) ||
                entry.normalizedForms.includes(candidate),
            );
            if (matches.length > 0) {
              return { query: candidate, count: matches.length };
            }
          }
          return null;
        })();

  const handleLoadMore = () => void setCurrentPage((prev) => prev + 1);

  const summaryMessage = (() => {
    if (loading) return 'Loading dictionary...';
    if (error) return 'Failed to load data.';
    if (sortedWords.length === 0) return 'No entries match your search.';

    const shown = Math.min(sortedWords.length, currentPage * RESULTS_PER_PAGE);
    const total = sortedWords.length;
    const plural = total === 1 ? 'entry' : 'entries';
    return `Showing ${shown} of ${total} ${plural}.`;
  })();

  const displayedEntries = sortedWords.slice(0, currentPage * RESULTS_PER_PAGE);

  return (
    <>
      <title>{`${normalizedQuery ? `${normalizedQuery} | ` : ''}Ukrainian Dictionary`}</title>
      <header className="topbar">
        <p className="brand__title">
          <div className="brand__title-line brand__title-line--blue">
            Ukrainian
          </div>
          <div className="brand__title-line brand__title-line--yellow">
            Dictionary
          </div>
        </p>

        <SearchBar />
      </header>

      <main className="main-content">
        <div className="list-status" aria-live="polite">
          <p id="resultCount">{summaryMessage}</p>
        </div>

        <section
          className="dictionary-list main"
          aria-label="Dictionary entries"
        >
          {loading && (
            <div
              className="row"
              style={{
                display: 'flex',
                justifyContent: 'center',
                padding: '2rem',
              }}
            >
              <p style={{ color: 'var(--muted)', fontWeight: 600 }}>
                Loading dictionary data...
              </p>
            </div>
          )}

          {error && (
            <div className="row" style={{ borderColor: 'var(--stress)' }}>
              <p style={{ color: 'var(--stress)', margin: 0 }}>
                Unable to load dictionary data: {error}
              </p>
            </div>
          )}

          {!loading &&
            !error &&
            displayedEntries.map((entry) => (
              <EntryRow
                key={entry.index}
                entry={entry}
                words={words}
                // highlight the original search term, not the normalized one
                query={q}
                // eslint-disable-next-line @typescript-eslint/no-misused-promises
                onSelectWord={setQuery}
              />
            ))}

          {!loading && !error && sortedWords.length === 0 && (
            <div className="row">
              <p style={{ margin: 0 }}>
                No results were found for this search.
              </p>
              {fallbackResult && (
                <button
                  type="button"
                  onClick={() => void setQuery(fallbackResult.query)}
                  className="button button--secondary"
                  style={{ marginTop: '0.75rem', width: 'fit-content' }}
                >
                  Search '{fallbackResult.query}' instead? (
                  {fallbackResult.count} results)
                </button>
              )}
              {normalizedQuery && (
                <p style={{ marginTop: '0.75rem', marginBottom: 0 }}>
                  <a
                    href={`https://en.wiktionary.org/wiki/${encodeURIComponent(normalizedQuery)}#Ukrainian`}
                    className="wiktionary-link"
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ fontWeight: 700 }}
                  >
                    Search Wiktionary for this word.
                  </a>
                </p>
              )}
            </div>
          )}

          {!loading &&
            !error &&
            sortedWords.length > displayedEntries.length && (
              <div className="load-more">
                <button
                  id="loadMore"
                  type="button"
                  onClick={handleLoadMore}
                  className="button button--primary"
                >
                  Show more
                </button>
              </div>
            )}
        </section>
      </main>

      <footer className="bottom-bar">
        <p></p>
      </footer>
    </>
  );
};

export default App;
