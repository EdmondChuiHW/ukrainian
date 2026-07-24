import type { FormValue } from '../types/words';

export const ACCENT_MARK = '\u0301';

export const isFormValue = (value: unknown): value is FormValue =>
  typeof value === 'string' || Array.isArray(value);

export const hasFormValue = (v: unknown): boolean => {
  if (v == null) return false;
  if (typeof v === 'string') return v.trim().length > 0;
  if (Array.isArray(v))
    return v.length > 0 && v.some((s) => typeof s === 'string' && s.trim().length > 0);
  return false;
};

export const normalizeText = (text: string = '') => {
  return text
    .toLowerCase()
    .replaceAll(ACCENT_MARK, '')
    .replaceAll('ї', 'і')
    .replaceAll('ґ', 'г')
    .replaceAll(/[“”«»„]/g, '"')
    .replaceAll(/[‘’‚‛‹›]/g, "'")
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9а-яєіїґ'\s-]+/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim();
};

export const getCellText = (value: unknown): string => {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return (value as unknown[]).join(' ');
  if (value && typeof value === 'object') {
    const extractTextArray = (val: unknown): string[] => {
      if (typeof val === 'string') return [val];
      if (Array.isArray(val))
        return (val as unknown[]).flatMap(extractTextArray);
      if (val && typeof val === 'object')
        return Object.values(val as Record<string, unknown>).flatMap(
          extractTextArray,
        );
      return [];
    };
    return extractTextArray(value).join(' ');
  }
  return '';
};

export const hasExactCellMatch = (value: unknown, query: string): boolean => {
  const normalizedQuery = normalizeText(query || '');
  if (!normalizedQuery) return false;

  const text = normalizeText(getCellText(value));
  if (!text) return false;

  let index = text.indexOf(normalizedQuery);
  while (index !== -1) {
    const end = index + normalizedQuery.length;
    const boundaryBefore = index === 0 || text[index - 1] === ' ';
    const boundaryAfter = end === text.length || text[end] === ' ';
    if (boundaryBefore && boundaryAfter) return true;
    index = text.indexOf(normalizedQuery, index + 1);
  }

  return false;
};

export const humanizeKey = (key: string): string => {
  const alias: { [key: string]: string } = {
    addl: 'Additional forms',
    comp: 'Comp.',
    super: 'Super.',
    arg: 'Argumentative',
    adv: 'Adv.',
    imp: 'Imp.',
    act: 'Act.',
    pas: 'Pass.',
    m: 'Male',
    n: 'Neuter',
    f: 'Female',
    s: 'Sing.',
    p: 'Plur.',
  };
  if (alias[key]) return alias[key];
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
    .replace(/\s+/g, ' ');
};

export function getHighlight(name: string): Highlight {
  return (
    CSS.highlights.get(name) ??
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    CSS.highlights.set(name, new Highlight()).get(name)!
  );
}
