import React, { useMemo } from 'react';
import MatchAndStressText from './MatchAndStressText';
import { ACCENT_MARK } from './utils';

interface CounterpartLinksProps {
  entry: any;
  verbAspectMap: any;
  words: any[];
  onSelectWord: (word: string) => void;
  query: string;
}

export const CounterpartLinks: React.FC<CounterpartLinksProps> = React.memo(
  ({ entry, verbAspectMap, words, onSelectWord, query }) => {
    const isVerb = entry.pos === 'verb';

    const counterparts = useMemo(() => {
      const rawAspectIds = verbAspectMap[entry.index.toString()];
      if (!rawAspectIds) return [];

      const aspectIds = Array.isArray(rawAspectIds)
        ? rawAspectIds
        : [rawAspectIds];
      return aspectIds.map((idx) => words[idx]).filter(Boolean);
    }, [entry.index, verbAspectMap, words]);

    if (!isVerb) return null;
    if (counterparts.length === 0) return null;

    const renderAspectLabel = () => {
      if (entry.info === 'impf') {
        return (
          <>Perfective counterpart{counterparts.length > 1 ? 's' : ''}: </>
        );
      }
      if (entry.info === 'pf') {
        return (
          <>Imperfective counterpart{counterparts.length > 1 ? 's' : ''}: </>
        );
      }
      return <>Aspect counterpart{counterparts.length > 1 ? 's' : ''}: </>;
    };

    return (
      <p style={{ marginTop: '1rem', marginBottom: 0 }}>
        {renderAspectLabel()}
        {counterparts.map((cp, idx) => {
          const noAccentWord = cp.word.replaceAll(ACCENT_MARK, '');
          return (
            <React.Fragment key={cp.index}>
              <a
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  onSelectWord(noAccentWord);
                }}
                className="counterpart-link"
                href={`/?q=${encodeURIComponent(noAccentWord)}`}
              >
                <MatchAndStressText text={cp.word} matchTerm={query} />
              </a>
              {idx < counterparts.length - 1 && ', '}
            </React.Fragment>
          );
        })}
      </p>
    );
  },
);

export default CounterpartLinks;
