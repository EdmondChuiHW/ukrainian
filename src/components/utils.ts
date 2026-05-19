export const ACCENT_MARK = '\u0301';

export const normalizeText = (text: string = '') => {
  return text
    .toString()
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

export const getCellText = (value: any): string => {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.join(' ');
  if (value && typeof value === 'object') {
    const extractTextArray = (val: any): string[] => {
      if (typeof val === 'string') return [val];
      if (Array.isArray(val)) return val.flatMap(extractTextArray);
      if (val && typeof val === 'object')
        return Object.values(val).flatMap(extractTextArray);
      return [];
    };
    return extractTextArray(value).join(' ');
  }
  return '';
};

export const hasExactCellMatch = (value: any, query: string): boolean => {
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
    comp: 'Comparative',
    super: 'Superlative',
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
