import React, { useMemo } from 'react';
import StressText from './StressText';

interface CounterpartLinksProps {
  entry: any;
  verbAspectMap: any;
  words: any[];
  onSelectWord: (word: string) => void;
}

export const CounterpartLinks: React.FC<CounterpartLinksProps> = React.memo(
  ({ entry, verbAspectMap, words, onSelectWord }) => {
    const isVerb = entry.pos === 'verb';
    if (!isVerb) return null;

    const counterparts = useMemo(() => {
      const rawAspectIds = verbAspectMap[entry.index.toString()];
      if (!rawAspectIds) return [];

      const aspectIds = Array.isArray(rawAspectIds)
        ? rawAspectIds
        : [rawAspectIds];
      return aspectIds.map((idx) => words[idx]).filter(Boolean);
    }, [entry.index, verbAspectMap, words]);

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
        {counterparts.map((cp, idx) => (
          <React.Fragment key={cp.index}>
            <button
              type="button"
              onClick={() => onSelectWord(cp.word)}
              className="counterpart-link"
              style={{
                background: 'none',
                border: 'none',
                padding: 0,
                color: 'var(--accent)',
                cursor: 'pointer',
                font: 'inherit',
                textDecoration: 'underline',
                fontWeight: 700,
              }}
            >
              <StressText text={cp.word} />
            </button>
            {idx < counterparts.length - 1 && ', '}
          </React.Fragment>
        ))}
      </p>
    );
  },
);

export default CounterpartLinks;
