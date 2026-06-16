import React, { Fragment } from 'react';
import MatchAndStressText from './MatchAndStressText';
import AspectCounterpartLinks from './AspectCounterpartLinks';
import FormsTable from './FormsTable';
import type { DictionaryEntry } from '../types/words';
import { SynonymLinks } from './SynonymLinks';

interface EntryRowProps {
  entry: DictionaryEntry;
  words: Array<Pick<DictionaryEntry, 'index' | 'word'>>;
  query: string;
  onSelectWord: (word: string) => void;
}

interface DefinitionItem {
  def: string;
  inlineTags?: string;
  index: number;
  synonyms?: Array<number | string>;
}

interface GroupedDef {
  qualifier?: string;
  items: Array<GroupedDef | DefinitionItem>;
}

const countTagFrequencies = (
  definitions: Array<{ def: string; tags: string[] }>,
): Map<string, number> => {
  const counts = new Map<string, number>();
  for (const { tags } of definitions) {
    for (const tag of tags) {
      counts.set(tag, (counts.get(tag) ?? 0) + 1);
    }
  }
  return counts;
};

const getMostFrequentTag = (
  definitions: Array<{ def: string; tags: string[] }>,
): string | null => {
  const counts = countTagFrequencies(definitions);
  if (counts.size === 0) return null;

  let maxTag: string | null = null;
  let maxCount = 0;

  for (const [tag, count] of counts.entries()) {
    if (count > maxCount) {
      maxCount = count;
      maxTag = tag;
    }
  }

  return maxCount > 1 ? maxTag : null;
};

const buildGroupedDefinitions = (
  definitions: Array<{
    def: string;
    tags: string[];
    index: number;
    synonyms?: Array<number | string>;
  }>,
): Array<GroupedDef | DefinitionItem> => {
  const mostFrequentTag = getMostFrequentTag(definitions);

  if (!mostFrequentTag) {
    return definitions.map(({ def, tags, index, synonyms }) => ({
      def,
      inlineTags: tags.length > 0 ? tags.join(', ') : undefined,
      index,
      synonyms,
    }));
  }

  const groupedByTag: Array<{
    def: string;
    tags: string[];
    hasTag: boolean;
    originalIndex: number;
    index: number;
    synonyms?: Array<number | string>;
  }> = definitions.map((d, idx) => ({
    ...d,
    hasTag: d.tags.includes(mostFrequentTag),
    originalIndex: idx,
  }));

  const firstWithTagIdx = groupedByTag.findIndex((d) => d.hasTag);
  const firstWithoutTagIdx = groupedByTag.findIndex((d) => !d.hasTag);

  const withTag = groupedByTag
    .filter((d) => d.hasTag)
    .map(({ def, tags, index, synonyms }) => ({
      def,
      tags: tags.filter((t) => t !== mostFrequentTag),
      index,
      synonyms,
    }));

  const withoutTag = groupedByTag
    .filter((d) => !d.hasTag)
    .map(({ def, tags, index, synonyms }) => ({
      def,
      tags,
      index,
      synonyms,
    }));

  const items: Array<GroupedDef | DefinitionItem> = [];

  if (
    firstWithoutTagIdx !== -1 &&
    (firstWithTagIdx === -1 || firstWithoutTagIdx < firstWithTagIdx)
  ) {
    const itemsWithoutTag = buildGroupedDefinitions(withoutTag);
    items.push(...itemsWithoutTag);

    if (withTag.length > 0) {
      const subItems = buildGroupedDefinitions(withTag);
      items.push({
        qualifier: `(${mostFrequentTag})`,
        items: subItems,
      });
    }
  } else {
    if (withTag.length > 0) {
      const subItems = buildGroupedDefinitions(withTag);
      items.push({
        qualifier: `(${mostFrequentTag})`,
        items: subItems,
      });
    }

    if (withoutTag.length > 0) {
      const itemsWithoutTag = buildGroupedDefinitions(withoutTag);
      items.push(...itemsWithoutTag);
    }
  }

  return items;
};

const groupDefinitions = (
  defs: string[],
  prefixes?: (string[] | null)[],
  defSynonyms?: Array<Array<number | string>>,
): Array<GroupedDef | DefinitionItem> => {
  const definitions = defs.map((def, idx) => {
    const prefix = prefixes?.[idx] || [];
    return { def, tags: prefix, index: idx, synonyms: defSynonyms?.[idx] };
  });

  return buildGroupedDefinitions(definitions);
};

const buildWiktionaryUrl = (word: string, lang: string = 'Ukrainian') => {
  const normalizedWord = word.replaceAll('\u0301', '').trim();
  return [
    `https://en.wiktionary.org/wiki/${encodeURIComponent(normalizedWord)}#${encodeURIComponent(lang)}`,
    normalizedWord,
  ] as const;
};

const formatGrammar = (entry: DictionaryEntry): string | null => {
  if (entry.grammar) {
    const parts: string[] = [];
    if (entry.grammar.gender) parts.push(entry.grammar.gender);

    const animacy =
      entry.grammar.animacy || (entry.pos === 'noun' ? 'inanimate' : null);
    if (animacy) parts.push(animacy);

    if (entry.grammar.aspect) parts.push(entry.grammar.aspect);
    return parts.length > 0 ? parts.join(', ') : null;
  }
  return entry.info || null;
};

export const EntryRow: React.FC<EntryRowProps> = ({
  entry,
  words,
  query,
  onSelectWord,
}) => {
  const [wiktionaryUrl, wiktionaryWord] = entry.reverse_translation_source_word
    ? buildWiktionaryUrl(entry.reverse_translation_source_word, 'English')
    : buildWiktionaryUrl(entry.word);
  const grammarDisplay = formatGrammar(entry);

  return (
    <article className="row">
      <div className="col entry-word-column">
        <div className="title-container">
          {entry.index}
          <h2 className="title">
            <MatchAndStressText text={entry.word} matchTerm={query} />
            {entry.variants?.map((v) => (
              <Fragment key={v}>
                <span> or </span>
                <MatchAndStressText text={v} matchTerm={query} />
              </Fragment>
            ))}
          </h2>
          <span className="subtitle">
            {entry.pos}
            {grammarDisplay && ` (${grammarDisplay})`}
          </span>

          <AspectCounterpartLinks
            entry={entry}
            words={words}
            onSelectWord={onSelectWord}
            query={query}
          />
        </div>

        {entry.defs && entry.defs.length > 0 && (
          <ol className="entry-list">
            {(() => {
              const renderItems = (
                items: Array<GroupedDef | DefinitionItem>,
                depth = 0,
              ): React.ReactNode => {
                return items.map((item, idx) => {
                  const isGrouped = 'qualifier' in item && 'items' in item;

                  if (isGrouped) {
                    const grouped = item;
                    return (
                      <li key={`${depth}-${idx}`}>
                        <span>{grouped.qualifier}</span>
                        <ol>{renderItems(grouped.items, depth + 1)}</ol>
                      </li>
                    );
                  } else {
                    const plain = item as DefinitionItem;
                    return (
                      <li key={`${depth}-${idx}`}>
                        {plain.inlineTags && <span>({plain.inlineTags}) </span>}
                        <MatchAndStressText
                          text={plain.def}
                          matchTerm={query}
                          lang="en"
                          className="definition"
                        />
                        {!!plain.synonyms?.length && (
                          <ul>
                            <li>
                              <SynonymLinks
                                type="def"
                                defIndex={idx}
                                entry={entry}
                                words={words}
                                onSelectWord={onSelectWord}
                                query={query}
                              />
                            </li>
                          </ul>
                        )}
                      </li>
                    );
                  }
                });
              };

              const groupDefs = groupDefinitions(
                entry.defs,
                entry.def_prefixes,
                entry.def_synonyms,
              );

              if (entry.reverse_translation_source_word) {
                return renderItems([
                  {
                    qualifier: `Translation of “${entry.reverse_translation_source_word}”`,
                    items: groupDefs,
                  },
                ]);
              }

              return renderItems(groupDefs);
            })()}
          </ol>
        )}

        <SynonymLinks
          type="entry"
          entry={entry}
          words={words}
          onSelectWord={onSelectWord}
          query={query}
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
          View “{wiktionaryWord}” on Wiktionary
        </a>
      </p>
    </article>
  );
};

export default EntryRow;
