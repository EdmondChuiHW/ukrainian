import React from 'react';
import CasesTable from './CasesTable';
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
import { CONFIGS } from './CasesTableConfigs';

interface FormsTableProps {
  posHint: string;
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

const isAdjectiveForms = (
  posHint: string,
  forms: DictionaryForms,
): forms is AdjectiveForms => {
  if (posHint === 'adjective') return true;

  const keys = Object.keys(forms);
  return keys.some(
    (key) =>
      /^(nom|acc|gen|dat|ins|loc) (am|an|af|ap)$/.test(key) &&
      isFormValue(forms[key]),
  );
};

const isVerbForms = (
  posHint: string,
  forms: DictionaryForms,
): forms is VerbForms => {
  if (posHint === 'verb') return true;

  return ['inf', 'pres', 'past', 'fut', 'imp'].some((key) => key in forms);
};

const BaseFormsTable: React.FC<FormsTableProps> = ({
  posHint,
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
      <CasesTable forms={forms} query={query} config={CONFIGS.SIMPLE_NOUN} />
    );
  }

  if (isNounForms(forms)) {
    return <CasesTable forms={forms} query={query} config={CONFIGS.NOUN} />;
  }

  if (isAdjectiveForms(posHint, forms)) {
    const config = CONFIGS.ADJECTIVE;
    const { columns, cases } = config;
    const visibleColCount = columns.filter(({ suffix }) =>
      cases.some((c) => hasFormValue(forms[`${c.key} ${suffix}`])),
    ).length;

    return (
      <CasesTable forms={forms} query={query} config={config}>
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

  if (isVerbForms(posHint, forms)) {
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
  forms_source,
  ...rest
}) => {
  return (
    <>
      <BaseFormsTable {...rest} />
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
