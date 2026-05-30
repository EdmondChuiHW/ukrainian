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
    ?.map((idx) => words[idx])
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
          <Fragment key={cp.index}>
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
          </Fragment>
        );
      })}
    </span>
  );
};

export default CounterpartLinks;
