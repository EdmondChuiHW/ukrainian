export interface Column {
  suffix: string;
  label: string;
  tooltip: string;
}

export interface CaseRow {
  key: string;
  label: string;
  tooltip: string;
}

const c = (key: string, label: string, tooltip: string): CaseRow => ({
  key,
  label,
  tooltip,
});

const NOUN_CASES: CaseRow[] = [
  c('nom', 'Nom.', 'Nominative/Називний — what/who?'),
  c('acc', 'Acc.', 'Accusative/Знахідний — what/whom?'),
  c('gen', 'Gen.', 'Genitive/Родовий — of what/whom?'),
  c('dat', 'Dat.', 'Dative/Давальний — to/for what/whom?'),
  c('ins', 'Ins.', 'Instrumental/Орудний — by/with what/whom?'),
  c('loc', 'Loc.', 'Locative/Місцевий — in/on what/whom?'),
  c('voc', 'Voc.', 'Vocative/Кличний — direct address'),
];

const ADJ_CASES: CaseRow[] = NOUN_CASES.filter(({ key }) => key !== 'voc');

const SIMPLE_NOUN_COLUMNS: Column[] = [{ suffix: 'n', label: '', tooltip: '' }];

const NOUN_COLUMNS: Column[] = [
  { suffix: 'ns', label: 'Sing.', tooltip: 'Singular/Однина' },
  { suffix: 'np', label: 'Plur.', tooltip: 'Plural/Множина' },
];

const ADJ_COLUMNS: Column[] = [
  { suffix: 'am', label: 'Male', tooltip: 'Male/Чоловічий' },
  { suffix: 'an', label: 'Neut.', tooltip: 'Neuter/Середній' },
  { suffix: 'af', label: 'Fem.', tooltip: 'Female/Жіночий' },
  { suffix: 'ap', label: 'Plur.', tooltip: 'Plural/Множина' },
];

export const CONFIGS = {
  NOUN: {
    type: 'noun',
    cases: NOUN_CASES,
    columns: NOUN_COLUMNS,
  },
  SIMPLE_NOUN: {
    type: 'simpleNoun',
    cases: NOUN_CASES,
    columns: SIMPLE_NOUN_COLUMNS,
  },
  ADJECTIVE: {
    type: 'adjective',
    cases: ADJ_CASES,
    columns: ADJ_COLUMNS,
  },
} as const;

export type CasesTableConfig = (typeof CONFIGS)[keyof typeof CONFIGS];
