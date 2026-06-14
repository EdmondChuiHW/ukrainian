import React, { useEffect } from 'react';
import { getHighlight } from './utils';

interface MatchAndStressTextProps {
  text: string;
  matchTerm?: string;
  lang?: string;
  className?: string;
}

const ACCENT_MARK = '\u0301';

export const MatchAndStressText: React.FC<MatchAndStressTextProps> = ({
  text,
  matchTerm,
  lang = 'uk',
  className,
}) => {
  const ref = React.useRef<HTMLSpanElement>(null);

  const [stressIndexes, normalizedText] = useStressHighlight(text);
  const matchIndexes = useMatchHighlight(normalizedText, matchTerm);

  // In Safari, the order of insertion matters,
  // i.e. `stress` must come after `search-match` if we want `stress` to be on top
  useHighlightRanges('search-match', ref, matchIndexes);
  useHighlightRanges('stress', ref, stressIndexes);

  return (
    <span
      ref={ref}
      aria-label={normalizedText !== text ? text : undefined}
      lang={lang}
      className={className}
    >
      {normalizedText}
    </span>
  );
};

function useStressHighlight(inputText: string) {
  'use memo';

  // Split accent marks so we can "see" it.
  // e.g. Богдáна (precomposed, length==7) -> Богда́на (decomposed, length==8)
  const text = inputText.normalize('NFD');
  let offset = 0;
  const stressIndexes: [number, number][] = [];
  let normalizedText = '';
  // Collect all indexes of stress marks in the text.
  // The indexes should be offset based on the deleted text.
  // Walk backwards so we find the stress mark first,
  // then we find the first non-empty char.
  for (let i = text.length - 1; i >= 0; i--) {
    if (text[i] !== ACCENT_MARK) {
      normalizedText = text[i] + normalizedText;
      continue;
    }

    // sometimes, the accent is preceded by a space due to bad data,
    // e.g. expected: "з'їси́", actual: "з'їси ́" (between 'и' and ' ́')
    // so we need to remove that space
    // and treat the prev char as the stressed one
    while (text[i - 1] === ' ' && i > 0) {
      i -= 1;
    }

    const end = i - offset;
    const start = end - 1;
    stressIndexes.push([start, end]);

    offset += 1;
  }

  return [stressIndexes, normalizedText] as const;
}

function useMatchHighlight(text: string, matchTerm?: string) {
  'use memo';

  const matchIndexes: [number, number][] = [];
  if (!matchTerm) return matchIndexes;

  const noAccents = matchTerm.replaceAll(ACCENT_MARK, '').trim();
  const matches = text.matchAll(new RegExp(RegExp.escape(noAccents), 'gi'));

  for (const match of matches) {
    matchIndexes.push([match.index, match.index + noAccents.length]);
  }

  return matchIndexes;
}

function useHighlightRanges<T extends HTMLElement | null>(
  highlightKey: string,
  ref: React.RefObject<T>,
  indexRanges: [number, number][],
) {
  useEffect(() => {
    if (!ref.current) return;

    const textNode = ref.current.firstChild;
    if (textNode?.nodeType !== Node.TEXT_NODE) return;

    const highlight = getHighlight(highlightKey);

    const ranges: Range[] = [];

    for (const [start, end] of indexRanges) {
      const range = new Range();
      try {
        range.setStart(textNode, start);
        range.setEnd(textNode, end);
        ranges.push(range);
      } catch (e: unknown) {
        // TODO log this or display CTA in the UI to report this
        console.warn(
          'Failed to set highlight range. Please open a GitHub issue',
          {
            start,
            end,
            text: textNode.textContent,
            error: e,
          },
        );
      }
    }

    ranges.forEach((range) => highlight.add(range));

    return () => ranges.forEach((range) => highlight.delete(range));
  }, [highlightKey, indexRanges, ref]);
}

MatchAndStressText.displayName = 'MatchAndStressText';

export default MatchAndStressText;
