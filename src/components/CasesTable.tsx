import React from 'react';
import FormCell from './FormCell';
import { hasFormValue, isFormValue } from './utils';
import type { DictionaryForms } from '../types/words';

interface Column {
  suffix: string;
  label: string;
  tooltip: string;
}

interface CaseRow {
  key: string;
  label: string;
  tooltip: string;
}

const c = (key: string, label: string, tooltip: string): CaseRow => ({ key, label, tooltip });

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

const SIMPLE_NOUN_COLUMNS: Column[] = [
  { suffix: 'n', label: '', tooltip: '' },
];

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

export { NOUN_CASES, ADJ_CASES, SIMPLE_NOUN_COLUMNS, NOUN_COLUMNS, ADJ_COLUMNS };

interface CasesTableProps {
  forms: DictionaryForms;
  query: string;
  cases: CaseRow[];
  columns: Column[];
  children?: React.ReactNode;
}

export const CasesTable: React.FC<CasesTableProps> = ({
  forms,
  query,
  cases,
  columns,
  children,
}) => {
  const visibleColumns = columns.filter(({ suffix }) =>
    cases.some((c) => hasFormValue(forms[`${c.key} ${suffix}`])),
  );

  const showHeader = visibleColumns.some((col) => col.label);

  return (
    <table className="form-table">
      {showHeader && (
        <thead>
          <tr className="table-header">
            <th></th>
            {visibleColumns.map(({ suffix, label, tooltip }) => (
              <th
                key={suffix}
                data-tooltip-id="table-col-header-tooltip"
                data-tooltip-content={tooltip}
              >
                {label}
              </th>
            ))}
          </tr>
        </thead>
      )}
      <tbody>
        {cases.map(({ key: caseKey, label: caseLabel, tooltip: caseTooltip }) => (
          <tr key={caseKey}>
            <th
              scope="row"
              className="form-cell-label"
              data-tooltip-id="table-row-header-tooltip"
              data-tooltip-content={caseTooltip}
            >
              {caseLabel}
            </th>
            {visibleColumns.map(({ suffix }) => {
              const rawValue = forms[`${caseKey} ${suffix}`];
              const val = isFormValue(rawValue) ? rawValue : [];
              return <FormCell key={suffix} value={val} query={query} />;
            })}
          </tr>
        ))}
        {children}
      </tbody>
    </table>
  );
};

export default CasesTable;
