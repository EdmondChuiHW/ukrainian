const ACCENT_MARK = '\u0301';
const COMBINING_MARK_RE = /\p{M}/u;

function isCombiningMark(char: string): boolean {
  return COMBINING_MARK_RE.test(char);
}

export function computeStressRanges(
  inputText: string,
): [stressIndexes: [number, number][], normalizedText: string] {
  // Split accent marks so we can "see" them.
  // e.g. Богдáна (precomposed, length==7) -> Богда́на (decomposed, length==8)
  const text = inputText
    .normalize('NFD')
    // sometimes, the accent is preceded by a space due to bad data,
    // e.g. expected: "з'їси́", actual: "з'їси ́" (between 'и' and ' ́')
    // so we remove that space
    .replace(/\s+\u0301/g, '\u0301');

  const stressIndexes: [number, number][] = [];
  const normalizedChars: string[] = [];

  for (const char of text) {
    if (char !== ACCENT_MARK) {
      normalizedChars.push(char);
      continue;
    }

    // end is the position after the last char added to normalizedChars.
    // The stressed grapheme cluster may span multiple codepoints when
    // combining marks are present (e.g. ї NFD → і + ̈).
    // Walk backwards past any combining marks to find the base character,
    // then include it to produce the full [start, end) range.
    const end = normalizedChars.length;
    if (end === 0) continue;

    let start = end;
    while (start > 0 && isCombiningMark(normalizedChars[start - 1])) {
      start--;
    }
    if (start === end) {
      start = end - 1;
    } else {
      start = start - 1;
    }

    stressIndexes.push([start, end]);
  }

  return [stressIndexes, normalizedChars.join('')];
}

export function computeMatchRanges(
  text: string,
  matchTerm?: string,
): [number, number][] {
  const matchIndexes: [number, number][] = [];
  if (!matchTerm) return matchIndexes;

  const noAccents = matchTerm
    .normalize('NFD')
    .replaceAll(ACCENT_MARK, '')
    .trim();
  if (!noAccents) return matchIndexes;
  const matches = text.matchAll(new RegExp(RegExp.escape(noAccents), 'gi'));

  for (const match of matches) {
    matchIndexes.push([match.index, match.index + noAccents.length]);
  }

  return matchIndexes;
}
