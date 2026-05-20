import React, {
  useState,
  useEffect,
  useMemo,
  useDeferredValue,
  useCallback,
} from 'react';
import { useQueryState } from 'nuqs';
import SearchBar from './components/SearchBar';
import EntryRow from './components/EntryRow';
import { normalizeText } from './components/utils';

export interface DictionaryEntry {
  index: number;
  word: string;
  pos: string;
  info?: string;
  defs?: string[];
  forms?: unknown;
  normalizedWord: string;
  normalizedDefs: string;
  normalizedForms: string;
  normalizedFormTokens: string[];
}

export interface RawDictionaryEntry {
  word: string;
  pos: string;
  info?: string;
  defs?: string[];
  forms?: unknown;
  freq?: number;
  index?: number;
}

export interface VerbAspectMap {
  [key: string]: number | number[];
}

const RESULTS_PER_PAGE = 50;

const exactMatchScore = (entry: DictionaryEntry, query: string): number => {
  if (!query) return 0;
  if (entry.normalizedWord === query) return 4;
  if (entry.normalizedFormTokens.includes(query)) return 3;
  if (
    entry.normalizedWord.startsWith(`${query} `) ||
    entry.normalizedWord.endsWith(` ${query}`) ||
    entry.normalizedWord.includes(` ${query} `)
  )
    return 3;
  if (
    entry.normalizedDefs.includes(query) ||
    entry.normalizedForms.includes(query)
  )
    return 2;
  if (entry.normalizedWord.includes(query)) return 1;
  return 0;
};

const extractTextArray = (value: unknown): string[] => {
  if (typeof value === 'string') return [value];
  if (Array.isArray(value)) return value.flatMap(extractTextArray);
  if (value && typeof value === 'object')
    return Object.values(value).flatMap(extractTextArray);
  return [];
};

const buildIndex = (
  entry: RawDictionaryEntry,
  index: number,
): DictionaryEntry => {
  const formTokens = extractTextArray(entry.forms)
    .map((val) => normalizeText(val))
    .filter(Boolean);
  const normalizedForms = formTokens.join(' ');
  return {
    ...entry,
    index,
    normalizedWord: normalizeText(entry.word),
    normalizedDefs: normalizeText(entry.defs?.join(' ') ?? ''),
    normalizedForms,
    normalizedFormTokens: formTokens,
  };
};

export const App: React.FC = () => {
  const [q, setQ] = useQueryState('q', { defaultValue: '' });
  const deferredQ = useDeferredValue(q);

  const [words, setWords] = useState<DictionaryEntry[]>([]);
  const [verbAspectMap, setVerbAspectMap] = useState<VerbAspectMap>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);

  // Sync dark theme directly to documentElement (html)
  useEffect(() => {
    const syncTheme = () => {
      const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      document.documentElement.classList.remove('theme-light', 'theme-dark');
      document.documentElement.classList.add(
        isDark ? 'theme-dark' : 'theme-light',
      );
    };
    syncTheme();
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    media.addEventListener('change', syncTheme);
    return () => media.removeEventListener('change', syncTheme);
  }, []);

  // Fetch data on mount
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        // fetch relative to host from workspace root
        const [wordsRes, aspectRes] = await Promise.all([
          fetch('/words.json'),
          fetch('/verb_aspect_mapping.json'),
        ]);

        if (!wordsRes.ok || !aspectRes.ok) {
          throw new Error('Failed to load dictionary data files');
        }

        const rawWords = (await wordsRes.json()) as RawDictionaryEntry[];
        const aspectMap = (await aspectRes.json()) as VerbAspectMap;

        const indexedWords = rawWords.map((entry, idx) =>
          buildIndex(entry, idx),
        );
        setWords(indexedWords);
        setVerbAspectMap(aspectMap);
        setError(null);
      } catch (err: unknown) {
        console.error(err);
        const errorMessage = err instanceof Error ? err.message : String(err);
        setError(errorMessage);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, []);

  // Reset page when search query changes by updating page from the interaction handlers.
  useEffect(() => {
    const onMessage = (ev: MessageEvent<{ q: string }>): void => {
      if (!ev.data?.q) return;
      if (ev.source !== window.opener) return;

      setQ(ev.data.q);
    };
    window.addEventListener('message', onMessage);

    return () => window.removeEventListener('message', onMessage);
  }, [setQ]);

  // Handle word selection (Counterparts, Wiktionary, etc.)
  const handleSelectWord = useCallback(
    (word: string) => {
      setQ(word || null, { shallow: true });
    },
    [setQ],
  );

  // Compute matched items
  const filteredWords = useMemo(() => {
    const query = normalizeText(deferredQ);
    if (!query) return words;

    return words.filter((entry) => {
      return (
        entry.normalizedWord.includes(query) ||
        entry.normalizedDefs.includes(query) ||
        entry.normalizedForms.includes(query)
      );
    });
  }, [words, deferredQ]);

  // Sort matched items
  const sortedWords = useMemo(() => {
    const query = normalizeText(deferredQ);
    if (!query) {
      return filteredWords; // already implicitly sorted by frequency index
    }
    return [...filteredWords].sort((a, b) => {
      const scoreA = exactMatchScore(a, query);
      const scoreB = exactMatchScore(b, query);
      if (scoreB !== scoreA) return scoreB - scoreA;
      return a.index - b.index;
    });
  }, [filteredWords, deferredQ]);

  // Compute suffix fallbacks
  // eslint-disable-next-line react-hooks/preserve-manual-memoization
  const fallbackResult = useMemo(() => {
    const query = normalizeText(deferredQ);
    if (filteredWords.length > 0 || !query) return null;

    let candidate = query;
    while (candidate) {
      candidate = candidate.slice(0, -1).trim();
      if (!candidate) break;

      const matches = words.filter(
        (entry) =>
          entry.normalizedWord.includes(candidate) ||
          entry.normalizedDefs.includes(candidate) ||
          entry.normalizedForms.includes(candidate),
      );
      if (matches.length > 0) {
        return { query: candidate, count: matches.length };
      }
    }
    return null;
  }, [words, filteredWords, deferredQ]);

  // Load more handler
  const handleLoadMore = useCallback(() => {
    setCurrentPage((prev) => prev + 1);
  }, []);

  // Render status bar message
  const summaryMessage = useMemo(() => {
    if (loading) return 'Loading dictionary...';
    if (error) return 'Failed to load data.';
    if (sortedWords.length === 0) return 'No entries match your search.';

    const shown = Math.min(sortedWords.length, currentPage * RESULTS_PER_PAGE);
    const total = sortedWords.length;
    const plural = total === 1 ? 'entry' : 'entries';
    return `Showing ${shown} of ${total} ${plural}.`;
  }, [loading, error, sortedWords, currentPage]);

  const displayedEntries = useMemo(() => {
    return sortedWords.slice(0, currentPage * RESULTS_PER_PAGE);
  }, [sortedWords, currentPage]);

  return (
    <>
      <header className="topbar">
        <p className="brand__title">
          <span className="brand__title-line brand__title-line--blue">
            Ukrainian
          </span>
          <span className="brand__title-line brand__title-line--yellow">
            Dictionary
          </span>
        </p>

        <SearchBar
          onSearchChange={(val) => setQ(val || null, { shallow: true })}
        />
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
                verbAspectMap={verbAspectMap}
                words={words}
                query={deferredQ}
                onSelectWord={handleSelectWord}
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
                  onClick={() => handleSelectWord(fallbackResult.query)}
                  className="button button--secondary"
                  style={{ marginTop: '0.75rem', width: 'fit-content' }}
                >
                  Search '{fallbackResult.query}' instead? (
                  {fallbackResult.count} results)
                </button>
              )}
              {q && (
                <p style={{ marginTop: '0.75rem', marginBottom: 0 }}>
                  <a
                    href={`https://en.wiktionary.org/wiki/${encodeURIComponent(q.replaceAll('\u0301', '').trim())}#Ukrainian`}
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
