import React, { useEffect } from 'react';
import { getHighlight } from './utils';
import { computeStressRanges, computeMatchRanges } from './highlightRanges';

interface MatchAndStressTextProps {
  text: string;
  matchTerm?: string;
  lang?: string;
  className?: string;
}

export const MatchAndStressText: React.FC<MatchAndStressTextProps> = ({
  text,
  matchTerm,
  lang = 'uk',
  className,
}) => {
  const ref = React.useRef<HTMLSpanElement>(null);

  const [stressIndexes, normalizedText] = computeStressRanges(text);
  const matchIndexes = computeMatchRanges(normalizedText, matchTerm);

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
      if (start < 0 || end < 0 || start >= end) continue;
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

    return () => void ranges.forEach((range) => highlight.delete(range));
  }, [highlightKey, indexRanges, ref]);
}

MatchAndStressText.displayName = 'MatchAndStressText';

export default MatchAndStressText;
