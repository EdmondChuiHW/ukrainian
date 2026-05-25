import React, { useEffect } from 'react';
import { getHighlight } from './utils';

interface MatchAndStressTextProps {
  text: string;
  matchTerm?: string;
  lang?: string;
}

const ACCENT_MARK = '\u0301';

export const MatchAndStressText: React.FC<MatchAndStressTextProps> = ({
  text,
  matchTerm,
  lang = 'uk',
}) => {
  const ref = React.useRef<HTMLSpanElement>(null);

  const [stressIndexes, normalizedText] = useStressHighlight(text);
  const matchIndexes = useMatchHighlight(normalizedText, matchTerm);

  // In Safari, the order of insertion matters,
  // i.e. `stress` must come after `search-match` if we want `stress` to be on top
  useHighlightRanges('search-match', ref, matchIndexes);
  useHighlightRanges('stress', ref, stressIndexes);

  return (
    <span ref={ref} aria-label={text} lang={lang}>
      {normalizedText}
    </span>
  );
};

function useStressHighlight(text: string) {
  'use memo';

  const stressIndexes: [number, number][] = [];
  // collect all indexes of stress marks in the text
  // the indexes should be offset based on the deleted text
  for (let i = 0; i < text.length - 1; i++) {
    if (text[i + 1] !== ACCENT_MARK) continue;

    const offset = stressIndexes.length;
    const start = i - offset;
    const end = start + 1;
    stressIndexes.push([start, end]);
  }

  const normalizedText = text.replaceAll(ACCENT_MARK, '');

  return [stressIndexes, normalizedText] as const;
}

function useMatchHighlight(text: string, matchTerm?: string) {
  'use memo';

  const matchIndexes: [number, number][] = [];
  if (!matchTerm) return matchIndexes;

  const noAccents = matchTerm.replaceAll(ACCENT_MARK, '');
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
      range.setStart(textNode, start);
      range.setEnd(textNode, end);
      ranges.push(range);
    }

    ranges.forEach((range) => highlight.add(range));

    return () => ranges.forEach((range) => highlight.delete(range));
  }, [highlightKey, indexRanges, ref]);
}

MatchAndStressText.displayName = 'MatchAndStressText';

export default MatchAndStressText;
