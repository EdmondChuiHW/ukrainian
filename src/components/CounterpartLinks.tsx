import { Fragment, type FC } from 'react';
import MatchAndStressText from './MatchAndStressText';
import { ACCENT_MARK } from './utils';
import type { DictionaryEntry } from '../types/words';

type CounterpartLinksProps = {
  entry: DictionaryEntry;
  words: Array<Pick<DictionaryEntry, 'index' | 'word'>>;
  onSelectWord: (word: string) => void;
  query: string;
};

export const CounterpartLinks: FC<CounterpartLinksProps> = ({
  entry,
  words,
  onSelectWord,
  query,
}) => {
  const isVerb = entry.pos === 'verb';

  const counterparts = entry.counterparts
    ?.map((idx) =>
      typeof idx === 'string' ? { word: idx, index: null } : words[idx],
    )
    .filter(Boolean);

  if (!isVerb) return null;
  if (!counterparts?.length) return null;

  const renderAspectLabel = () => {
    const aspect = entry.grammar?.aspect;
    if (aspect === 'imperfective') {
      return <>Perfective: </>;
    }
    if (aspect === 'perfective') {
      return <>Imperfective: </>;
    }
    return <>Aspect counterpart{counterparts.length > 1 ? 's' : ''}: </>;
  };

  return (
    <span>
      {renderAspectLabel()}
      {counterparts.map((cp, idx) => {
        const noAccentWord = cp.word.replaceAll(ACCENT_MARK, '');
        return (
          <Fragment key={cp.index ?? `unknown-${idx}`}>
            <a
              type="button"
              onClick={(e) => {
                e.preventDefault();
                onSelectWord(noAccentWord);
              }}
              className={`counterpart-link ${cp.index === null ? ' missing' : ''}`}
              title={
                cp.word + (cp.index === null ? ` (entry does not exist)` : '')
              }
              href={`/?q=${encodeURIComponent(noAccentWord)}`}
            >
              <MatchAndStressText text={cp.word} matchTerm={query} />
            </a>
            {idx < counterparts.length - 1 && ', '}
          </Fragment>
        );
      })}
    </span>
  );
};

export default CounterpartLinks;
