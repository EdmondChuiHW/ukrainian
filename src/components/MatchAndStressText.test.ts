import { describe, it, expect } from 'vitest';
import { computeStressRanges, computeMatchRanges } from './highlightRanges';

const ACCENT = '\u0301';
const DIAERESIS = '\u0308';
const BREVE = '\u0306';

// Cyrillic helpers for test data clarity
const CYR_A = '\u0430';
const CYR_B = '\u0431';
const CYR_YI = '\u0457'; // ї precomposed
const CYR_I = '\u0456'; // і
const CYR_Y = '\u0438'; // и
const CYR_SHORT_I = '\u0439'; // й

function stress(text: string): [[number, number][], string] {
  return computeStressRanges(text);
}

function match(text: string, matchTerm?: string): [number, number][] {
  return computeMatchRanges(text, matchTerm);
}

describe('useStressHighlight', () => {
  it('returns empty for plain text', () => {
    const [indexes, text] = stress('Богдана');
    expect(indexes).toEqual([]);
    expect(text).toBe('Богдана');
  });

  it('handles simple precomposed stress', () => {
    const input = `Богд${CYR_A}${ACCENT}на`;
    const [indexes, text] = stress(input);
    expect(text).toBe('Богдана');
    expect(indexes).toEqual([[4, 5]]);
  });

  it('handles simple decomposed stress', () => {
    const input = `Богда${ACCENT}на`;
    const [indexes, text] = stress(input);
    expect(text).toBe('Богдана');
    expect(indexes).toEqual([[4, 5]]);
  });

  it('handles ї (precomposed) with stress', () => {
    const input = `${CYR_YI}${ACCENT}жа`;
    const [indexes, text] = stress(input);
    // ї NFD → і + ̈
    expect(text).toBe(`${CYR_I}${DIAERESIS}жа`);
    expect(indexes).toEqual([[0, 2]]);
  });

  it('handles ї (NFD-equivalent input) with stress', () => {
    const input = `${CYR_I}${DIAERESIS}${ACCENT}жа`;
    const [indexes, text] = stress(input);
    expect(text).toBe(`${CYR_I}${DIAERESIS}жа`);
    expect(indexes).toEqual([[0, 2]]);
  });

  it('handles й (precomposed) with stress', () => {
    const input = `${CYR_SHORT_I}${ACCENT}ти`;
    const [indexes, text] = stress(input);
    // й NFD → и + ̆
    expect(text).toBe(`${CYR_Y}${BREVE}ти`);
    expect(indexes).toEqual([[0, 2]]);
  });

  it('handles multiple stressed chars', () => {
    const input = `${CYR_A}${ACCENT} ${CYR_B}${ACCENT}`;
    const [indexes, text] = stress(input);
    expect(text).toBe(`${CYR_A} ${CYR_B}`);
    expect(indexes).toEqual([
      [0, 1],
      [2, 3],
    ]);
  });

  it('removes whitespace before accent (bad data)', () => {
    const input = `${CYR_A} ${ACCENT}`;
    const [indexes, text] = stress(input);
    expect(text).toBe(CYR_A);
    expect(indexes).toEqual([[0, 1]]);
  });

  it('handles stress on the first char', () => {
    const input = `${CYR_A}${ACCENT}bc`;
    const [indexes, text] = stress(input);
    expect(text).toBe(`${CYR_A}bc`);
    expect(indexes).toEqual([[0, 1]]);
  });

  it('handles text with no accent marks', () => {
    const [indexes, text] = stress('no accents here');
    expect(indexes).toEqual([]);
    expect(text).toBe('no accents here');
  });

  it('handles empty string', () => {
    const [indexes, text] = stress('');
    expect(indexes).toEqual([]);
    expect(text).toBe('');
  });
});

describe('useMatchHighlight', () => {
  it('returns empty when no matchTerm', () => {
    expect(match('Богдана')).toEqual([]);
  });

  it('finds a simple match', () => {
    expect(match('Богдана', 'да')).toEqual([[3, 5]]);
  });

  it('finds overlapping matches', () => {
    // абаба with "ба" matches at positions 1 and 3
    expect(match(`абаба`, `ба`)).toEqual([
      [1, 3],
      [3, 5],
    ]);
  });

  it('is case insensitive', () => {
    expect(match('Богдана', 'бог')).toEqual([[0, 3]]);
  });

  it('matches ї when search term is precomposed', () => {
    const text = `${CYR_I}${DIAERESIS}жа`;
    // ї NFD → і + ̈ → 4 codepoints
    expect(match(text, 'їжа')).toEqual([[0, 4]]);
  });

  it('matches ї when search term is decomposed', () => {
    const text = `${CYR_I}${DIAERESIS}жа`;
    expect(match(text, `${CYR_I}${DIAERESIS}жа`)).toEqual([[0, 4]]);
  });

  it('matches й when search term is precomposed', () => {
    const text = `${CYR_Y}${BREVE}ти`;
    // й NFD → и + ̆ → 4 codepoints
    expect(match(text, 'йти')).toEqual([[0, 4]]);
  });

  it('ignores accent marks in search term', () => {
    expect(match('Богдана', `Богда${ACCENT}на`)).toEqual([[0, 7]]);
  });

  it('returns empty for accent-only search term', () => {
    expect(match('text', ACCENT)).toEqual([]);
  });

  it('returns no matches for non-matching term', () => {
    expect(match('Богдана', 'xyz')).toEqual([]);
  });
});
