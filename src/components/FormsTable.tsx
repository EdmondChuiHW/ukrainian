import React from 'react';
import CasesTable, {
  NOUN_CASES,
  ADJ_CASES,
  SIMPLE_NOUN_COLUMNS,
  NOUN_COLUMNS,
  ADJ_COLUMNS,
} from './CasesTable';
import MatchAndStressText from './MatchAndStressText';
import VerbTable from './VerbTable';
import type { VerbForms } from './VerbTable';
import GenericForms from './GenericForms';
import type {
  DictionaryForms,
  FormValue,
  AdjectiveForms,
  FormStatus,
} from '../types/words';
import { hasFormValue, humanizeKey, isFormValue } from './utils';
import { Tooltip } from 'react-tooltip';

interface FormsTableProps {
  forms?: DictionaryForms;
  forms_status: FormStatus;
  forms_source?: string;
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
  forms_status,
  query,
  showComplexFutureForms,
}) => {
  if (!forms || Object.keys(forms).length === 0) {
    if (forms_status === 'indeclinable') {
      return <p className="indec">Indeclinable</p>;
    }
    return <p className="indec">Unavailable</p>;
  }

  if (isSimpleNounForms(forms)) {
    return (
      <CasesTable
        forms={forms}
        query={query}
        cases={NOUN_CASES}
        columns={SIMPLE_NOUN_COLUMNS}
      />
    );
  }

  if (isNounForms(forms)) {
    return (
      <CasesTable
        forms={forms}
        query={query}
        cases={NOUN_CASES}
        columns={NOUN_COLUMNS}
      />
    );
  }

  if (isAdjectiveForms(forms)) {
    const visibleColCount = ADJ_COLUMNS.filter(({ suffix }) =>
      ADJ_CASES.some((c) => hasFormValue(forms[`${c.key} ${suffix}`])),
    ).length;

    return (
      <CasesTable
        forms={forms}
        query={query}
        cases={ADJ_CASES}
        columns={ADJ_COLUMNS}
      >
        {forms.addl &&
          Object.entries(forms.addl).map(([addlKey, addlValue]) => (
            <tr key={addlKey}>
              <th
                scope="row"
                className="form-cell-label"
                data-tooltip-id="table-row-header-tooltip"
              >
                {humanizeKey(addlKey)}
              </th>
              <td colSpan={visibleColCount}>
                {Array.isArray(addlValue) ? (
                  addlValue.map((item: string, idx: number) => (
                    <React.Fragment key={idx}>
                      <MatchAndStressText text={item} matchTerm={query} />
                      {idx < addlValue.length - 1 && <br />}
                    </React.Fragment>
                  ))
                ) : (
                  <MatchAndStressText text={addlValue} matchTerm={query} />
                )}
              </td>
            </tr>
          ))}
      </CasesTable>
    );
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
  forms_status,
  forms_source,
  query,
  showComplexFutureForms,
}) => {
  return (
    <>
      <BaseFormsTable
        forms={forms}
        forms_status={forms_status}
        query={query}
        showComplexFutureForms={showComplexFutureForms}
      />
      {forms_source ? (
        <p className="forms-source">Forms source: {forms_source}</p>
      ) : null}
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
