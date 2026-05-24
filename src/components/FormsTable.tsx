import React from 'react';
import SimpleNounTable from './SimpleNounTable';
import NounTable from './NounTable';
import AdjectiveTable from './AdjectiveTable';
import VerbTable from './VerbTable';
import type { VerbForms } from './VerbTable';
import GenericForms from './GenericForms';

interface FormsTableProps {
  forms: unknown;
  query: string;
}

const isSimpleNounForms = (forms: any): boolean => {
  if (!forms) return false;
  const keys = Object.keys(forms);
  if (!keys.length) return false;
  return keys.every((key) => /^(nom|acc|gen|dat|ins|loc|voc) n$/.test(key));
};

const isNounForms = (forms: any): boolean => {
  if (!forms) return false;
  const keys = Object.keys(forms);
  if (!keys.length) return false;
  return keys.every((key) =>
    /^(nom|acc|gen|dat|ins|loc|voc) (ns|np)$/.test(key),
  );
};

const isAdjectiveForms = (forms: any): boolean => {
  if (!forms) return false;
  const keys = Object.keys(forms);
  return keys.some((key) =>
    /^(nom|acc|gen|dat|ins|loc) (am|an|af|ap)$/.test(key),
  );
};

const isVerbForms = (forms: unknown): forms is VerbForms => {
  if (!forms || typeof forms !== 'object') return false;
  return ['inf', 'pres', 'past', 'fut', 'imp'].some((key) => key in forms);
};

export const FormsTable: React.FC<FormsTableProps> = ({ forms, query }) => {
  if (!forms || Object.keys(forms).length === 0) {
    return <p className="indec">Indeclinable</p>;
  }

  if (isSimpleNounForms(forms)) {
    return <SimpleNounTable forms={forms} query={query} />;
  }

  if (isNounForms(forms)) {
    return <NounTable forms={forms} query={query} />;
  }

  if (isAdjectiveForms(forms)) {
    return <AdjectiveTable forms={forms} query={query} />;
  }

  if (isVerbForms(forms)) {
    return <VerbTable forms={forms} query={query} />;
  }

  return <GenericForms forms={forms} query={query} />;
};

export default FormsTable;
