import { type FC } from 'react';
import type { DictionaryEntry } from '../types/words';
import RelatedWordLinks from './RelatedWordLinks';

type BaseSynonymLinksProps = {
  entry: DictionaryEntry;
  words: Array<Pick<DictionaryEntry, 'index' | 'word'>>;
  onSelectWord: (word: string) => void;
  query: string;
};

type SynonymLinksProps =
  | (BaseSynonymLinksProps & {
      type: 'entry';
      defIndex?: never;
    })
  | (BaseSynonymLinksProps & {
      type: 'def';
      defIndex: number;
    });

export const SynonymLinks: FC<SynonymLinksProps> = ({
  type,
  defIndex,
  entry,
  words,
  onSelectWord,
  query,
}) => {
  const items =
    type === 'entry' ? entry.synonyms : entry.def_synonyms?.[defIndex];
  if (!items?.length) return null;

  return (
    <RelatedWordLinks
      title="Synonyms: "
      items={items}
      className="synonym-link"
      words={words}
      onSelectWord={onSelectWord}
      query={query}
    />
  );
};

SynonymLinks.displayName = 'SynonymLinks';

export default SynonymLinks;
