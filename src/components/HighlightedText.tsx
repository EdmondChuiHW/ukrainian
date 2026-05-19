import type React from 'react';
import StressText from './StressText';
import { normalizeText } from './utils';

interface HighlightedTextProps {
  text: string;
  query: string;
}

export const HighlightedText: React.FC<HighlightedTextProps> = ({
  text,
  query,
}) => {
  if (!text) return null;

  const normalizedQuery = normalizeText(query);
  if (!normalizedQuery) return <StressText text={text} />;

  const textStr = text.toString();

  // Map each original index to its position in the normalized string
  const normalizedIndices: number[] = [];
  let normalizedAccumulator = '';

  for (let i = 0; i < textStr.length; i++) {
    const char = textStr[i];
    if (char === '\u0301') {
      normalizedIndices.push(
        normalizedIndices[normalizedIndices.length - 1] ?? 0,
      );
    } else {
      const normalizedChar = normalizeText(char);
      normalizedAccumulator += normalizedChar;
      normalizedIndices.push(normalizedAccumulator.length - 1);
    }
  }

  const normalizedTextStr = normalizeText(textStr);
  let startIdx = 0;
  let matchIdx = normalizedTextStr.indexOf(normalizedQuery, startIdx);

  const matchSegments: { start: number; end: number; isMatch: boolean }[] = [];

  while (matchIdx !== -1) {
    const matchEndIdx = matchIdx + normalizedQuery.length;

    // Map back to original indices
    const origStart = normalizedIndices.indexOf(matchIdx);
    const origEnd = normalizedIndices.lastIndexOf(matchEndIdx - 1) + 1;

    if (origStart !== -1 && origEnd !== -1 && origStart < origEnd) {
      if (origStart > startIdx) {
        matchSegments.push({ start: startIdx, end: origStart, isMatch: false });
      }
      matchSegments.push({ start: origStart, end: origEnd, isMatch: true });
      startIdx = origEnd;
    } else {
      // Fallback progress to avoid infinite loops if matching indices fail to resolve
      startIdx = Math.max(startIdx + 1, origEnd);
    }

    matchIdx = normalizedTextStr.indexOf(normalizedQuery, matchIdx + 1);
  }

  if (startIdx < textStr.length) {
    matchSegments.push({
      start: startIdx,
      end: textStr.length,
      isMatch: false,
    });
  }

  const segments = matchSegments.map((seg, idx) => ({
    key: `${idx}-${seg.start}-${seg.end}`,
    text: textStr.slice(seg.start, seg.end),
    isMatch: seg.isMatch,
  }));

  return (
    <>
      {segments.map((seg) =>
        seg.isMatch ? (
          <mark key={seg.key} className="match">
            <StressText text={seg.text} />
          </mark>
        ) : (
          <StressText key={seg.key} text={seg.text} />
        ),
      )}
    </>
  );
};

HighlightedText.displayName = 'HighlightedText';

export default HighlightedText;
