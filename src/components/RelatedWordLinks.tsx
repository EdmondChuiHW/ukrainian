import { Fragment, type FC } from 'react';
import MatchAndStressText from './MatchAndStressText';
import { ACCENT_MARK } from './utils';
import type { DictionaryEntry } from '../types/words';

type RelatedWordLinksProps = {
  title: React.ReactNode;
  items: Array<number | string>;
  className?: string;
  words: Array<Pick<DictionaryEntry, 'index' | 'word'>>;
  onSelectWord: (word: string) => void;
  query: string;
};

export const RelatedWordLinks: FC<RelatedWordLinksProps> = ({
  title,
  items,
  className,
  words,
  onSelectWord,
  query,
}) => {
  if (!items.length) return null;

  const resolveLinkItem = (item: number | string) => {
    if (typeof item === 'number') {
      const target = words[item];
      return target
        ? { word: target.word, index: item }
        : { word: String(item), index: null };
    }
    return { word: item, index: null };
  };

  return (
    <span>
      {title}
      {items
        .map(resolveLinkItem)
        .filter((item) => item.word)
        .map((item, idx) => {
          const noAccentWord = item.word.replaceAll(ACCENT_MARK, '');
          return (
            <Fragment key={item.index ?? `unknown-${idx}`}>
              <a
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  onSelectWord(noAccentWord);
                }}
                className={`${className}${item.index === null ? ' missing' : ''}`}
                title={
                  item.word +
                  (item.index === null ? ` (entry does not exist)` : '')
                }
                href={`/?q=${encodeURIComponent(noAccentWord)}`}
              >
                <MatchAndStressText text={item.word} matchTerm={query} />
              </a>
              {idx < items.length - 1 && ', '}
            </Fragment>
          );
        })}
    </span>
  );
};

RelatedWordLinks.displayName = 'RelatedWordLinks';

export default RelatedWordLinks;
