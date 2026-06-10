import { type FC } from 'react';
import type { DictionaryEntry } from '../types/words';
import RelatedWordLinks from './RelatedWordLinks';

type AspectCounterpartLinksProps = {
  entry: DictionaryEntry;
  words: Array<Pick<DictionaryEntry, 'index' | 'word'>>;
  onSelectWord: (word: string) => void;
  query: string;
};

export const AspectCounterpartLinks: FC<AspectCounterpartLinksProps> = ({
  entry,
  words,
  onSelectWord,
  query,
}) => {
  const items = entry.counterparts;
  if (!items?.length) return null;

  const aspect = entry.grammar?.aspect;
  const title =
    aspect === 'imperfective'
      ? 'Perfective: '
      : aspect === 'perfective'
        ? 'Imperfective: '
        : `Aspect counterpart${items.length > 1 ? 's' : ''}: `;

  return (
    <RelatedWordLinks
      title={title}
      items={items}
      className="counterpart-link"
      words={words}
      onSelectWord={onSelectWord}
      query={query}
    />
  );
};

AspectCounterpartLinks.displayName = 'AspectCounterpartLinks';

export default AspectCounterpartLinks;
