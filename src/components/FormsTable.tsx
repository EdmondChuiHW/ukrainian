import React from 'react';
import SimpleNounTable from './SimpleNounTable';
import NounTable from './NounTable';
import AdjectiveTable from './AdjectiveTable';
import VerbTable from './VerbTable';
import type { VerbForms } from './VerbTable';
import GenericForms from './GenericForms';
import type {
  DictionaryForms,
  FormValue,
  AdjectiveForms,
} from '../types/words';
import { isFormValue } from './utils';
import { Tooltip } from 'react-tooltip';

interface FormsTableProps {
  forms?: DictionaryForms;
  query: string;
  showComplexFutureForms?: boolean;
}

const isSimpleNounForms = (
  forms: DictionaryForms,
): forms is Record<string, FormValue> => {
  const keys = Object.keys(forms);
  if (!keys.length) return false;
  return keys.every(
    (key) =>
      /^(nom|acc|gen|dat|ins|loc|voc) n$/.test(key) && isFormValue(forms[key]),
  );
};

const isNounForms = (
  forms: DictionaryForms,
): forms is Record<string, FormValue> => {
  const keys = Object.keys(forms);
  if (!keys.length) return false;
  return keys.every(
    (key) =>
      /^(nom|acc|gen|dat|ins|loc|voc) (ns|np)$/.test(key) &&
      isFormValue(forms[key]),
  );
};

const isAdjectiveForms = (forms: DictionaryForms): forms is AdjectiveForms => {
  const keys = Object.keys(forms);
  return keys.some(
    (key) =>
      /^(nom|acc|gen|dat|ins|loc) (am|an|af|ap)$/.test(key) &&
      isFormValue(forms[key]),
  );
};

const isVerbForms = (forms: DictionaryForms): forms is VerbForms => {
  return ['inf', 'pres', 'past', 'fut', 'imp'].some((key) => key in forms);
};

const BaseFormsTable: React.FC<FormsTableProps> = ({
  forms,
  query,
  showComplexFutureForms,
}) => {
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
    return (
      <VerbTable
        forms={forms}
        query={query}
        showComplexFutureForms={showComplexFutureForms}
      />
    );
  }

  return <GenericForms forms={forms} query={query} />;
};

export const FormsTable: React.FC<FormsTableProps> = ({
  forms,
  query,
  showComplexFutureForms,
}) => {
  return (
    <>
      <BaseFormsTable
        forms={forms}
        query={query}
        showComplexFutureForms={showComplexFutureForms}
      />
      <Tooltip id="table-col-header-tooltip" place="top" className="tooltip" />
      <Tooltip
        id="table-row-header-tooltip"
        place="bottom-start"
        className="tooltip"
      />
      <Tooltip id="table-cell-tooltip" place="bottom" className="tooltip" />
    </>
  );
};

export default FormsTable;
