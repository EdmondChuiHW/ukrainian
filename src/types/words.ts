export type FormValue = string | string[];
export type DictionaryForms = Record<string, unknown>;
export type AdjectiveForms = DictionaryForms & {
  addl?: Record<string, FormValue>;
};

export interface RawDictionaryEntry {
  word: string;
  pos: string;
  info?: string;
  defs?: string[];
  forms?: DictionaryForms;
  variants?: string[];
  freq?: number;
  index?: number;
  counterparts?: number[];
}

export interface DictionaryEntry extends RawDictionaryEntry {
  index: number;
  normalizedWord: string;
  normalizedDefs: string;
  normalizedForms: string;
  normalizedFormTokens: string[];
}
