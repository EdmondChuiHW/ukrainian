export type FormValue = string | string[];
export type DictionaryForms = Record<string, unknown>;
export type AdjectiveForms = DictionaryForms & {
  addl?: Record<string, FormValue>;
};

export interface GrammarInfo {
  gender: string | null;
  animacy: string | null;
  aspect: string | null;
}

export interface RawDictionaryEntry {
  word: string;
  pos: string;
  info?: string;
  grammar?: GrammarInfo;
  defs?: string[];
  def_prefixes?: (string[] | null)[];
  def_synonyms?: Array<Array<number | string>>;
  forms?: DictionaryForms;
  variants?: string[];
  freq?: number;
  index?: number;
  synonyms?: Array<number | string>;
  counterparts?: number[];
  reverse_translation?: boolean;
  reverse_translation_source_word?: string;
}

export interface DictionaryEntry extends RawDictionaryEntry {
  index: number;
  normalizedWord: string;
  normalizedDefs: string;
  normalizedForms: string;
  normalizedFormTokens: string[];
  normalizedSynonyms: string;
  normalizedDefSynonyms: string;
  normalizedCounterparts: string;
}
