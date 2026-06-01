import React, { Fragment } from 'react';
import MatchAndStressText from './MatchAndStressText';
import CounterpartLinks from './CounterpartLinks';
import FormsTable from './FormsTable';
import type { DictionaryEntry } from '../types/words';

interface EntryRowProps {
  entry: DictionaryEntry;
  words: Array<Pick<DictionaryEntry, 'index' | 'word'>>;
  query: string;
  onSelectWord: (word: string) => void;
}

interface GroupedDef {
  qualifier?: string;
  items: Array<GroupedDef | { def: string; inlineTags?: string }>;
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
  definitions: Array<{ def: string; tags: string[] }>,
): Array<GroupedDef | { def: string; inlineTags?: string }> => {
  const mostFrequentTag = getMostFrequentTag(definitions);

  if (!mostFrequentTag) {
    return definitions.map(({ def, tags }) => ({
      def,
      inlineTags: tags.length > 0 ? tags.join(', ') : undefined,
    }));
  }

  const groupedByTag: Array<{
    def: string;
    tags: string[];
    hasTag: boolean;
    originalIndex: number;
  }> = definitions.map((d, idx) => ({
    ...d,
    hasTag: d.tags.includes(mostFrequentTag),
    originalIndex: idx,
  }));

  const firstWithTagIdx = groupedByTag.findIndex((d) => d.hasTag);
  const firstWithoutTagIdx = groupedByTag.findIndex((d) => !d.hasTag);

  const withTag = groupedByTag
    .filter((d) => d.hasTag)
    .map(({ def, tags }) => ({
      def,
      tags: tags.filter((t) => t !== mostFrequentTag),
    }));

  const withoutTag = groupedByTag
    .filter((d) => !d.hasTag)
    .map(({ def, tags }) => ({
      def,
      tags,
    }));

  const items: Array<GroupedDef | { def: string; inlineTags?: string }> = [];

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
): Array<GroupedDef | { def: string; inlineTags?: string }> => {
  const definitions = defs.map((def, idx) => {
    const prefix = prefixes?.[idx] || [];
    return { def, tags: prefix };
  });

  return buildGroupedDefinitions(definitions);
};

const buildWiktionaryUrl = (word: string = '') => {
  const normalizedWord = word.toString().replaceAll('\u0301', '').trim();
  return `https://en.wiktionary.org/wiki/${encodeURIComponent(normalizedWord)}#Ukrainian`;
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
  const wiktionaryUrl = buildWiktionaryUrl(entry.word);
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

          <CounterpartLinks
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
                items: Array<GroupedDef | { def: string; inlineTags?: string }>,
                depth = 0,
              ): React.ReactNode => {
                return items.map((item, idx) => {
                  const isGrouped = 'qualifier' in item && 'items' in item;

                  if (isGrouped) {
                    const grouped = item as GroupedDef;
                    return (
                      <li key={`${depth}-${idx}`}>
                        <span>{grouped.qualifier}</span>
                        <ol>{renderItems(grouped.items, depth + 1)}</ol>
                      </li>
                    );
                  } else {
                    const plain = item as { def: string; inlineTags?: string };
                    return (
                      <li key={`${depth}-${idx}`}>
                        {plain.inlineTags && <span>({plain.inlineTags}) </span>}
                        <MatchAndStressText
                          text={plain.def}
                          matchTerm={query}
                        />
                      </li>
                    );
                  }
                });
              };

              return renderItems(
                groupDefinitions(entry.defs, entry.def_prefixes),
              );
            })()}
          </ol>
        )}
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
};

export default EntryRow;
