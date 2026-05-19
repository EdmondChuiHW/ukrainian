import React from 'react';
import HighlightedText from './HighlightedText';
import CounterpartLinks from './CounterpartLinks';
import FormsTable from './FormsTable';

interface EntryRowProps {
  entry: any;
  verbAspectMap: any;
  words: any[];
  query: string;
  onSelectWord: (word: string) => void;
}

const buildWiktionaryUrl = (word: string = '') => {
  const normalizedWord = word.toString().replaceAll('\u0301', '').trim();
  return `https://en.wiktionary.org/wiki/${encodeURIComponent(normalizedWord)}#Ukrainian`;
};

export const EntryRow: React.FC<EntryRowProps> = React.memo(
  ({ entry, verbAspectMap, words, query, onSelectWord }) => {
    const wiktionaryUrl = buildWiktionaryUrl(entry.word);

    return (
      <article className="row">
        <div className="col entry-word-column">
          <div className="title-container">
            <h2 className="title">
              <HighlightedText text={entry.word} query={query} />
            </h2>
            <span className="subtitle">
              {entry.pos}
              {entry.info && ` (${entry.info})`}
            </span>
          </div>

          {entry.defs && entry.defs.length > 0 && (
            <ol className="entry-list">
              {entry.defs.map((def: string, idx: number) => (
                <li key={idx}>
                  <HighlightedText text={def} query={query} />
                </li>
              ))}
            </ol>
          )}

          <CounterpartLinks
            entry={entry}
            verbAspectMap={verbAspectMap}
            words={words}
            onSelectWord={onSelectWord}
          />
        </div>

        <div className="col entry-forms-column">
          <FormsTable forms={entry.forms} query={query} />
        </div>

        <p className="entry-link">
          <a
            href={wiktionaryUrl}
            className="wiktionary-link"
            target="_blank"
            rel="noopener noreferrer"
          >
            View on Wiktionary
          </a>
        </p>
      </article>
    );
  },
);

export default EntryRow;
