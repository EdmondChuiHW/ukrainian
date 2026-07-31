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

export {
  NOUN_CASES,
  ADJ_CASES,
  SIMPLE_NOUN_COLUMNS,
  NOUN_COLUMNS,
  ADJ_COLUMNS,
};

interface CasesTableProps {
  forms: DictionaryForms;
  query: string;
  cases: CaseRow[];
  columns: Column[];
  children?: React.ReactNode;
}

function normalizeValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value
      .map((v) => String(v).trim())
      .sort()
      .join('|');
  }
  if (typeof value === 'string') {
    return value.trim();
  }
  return '';
}

function valuesAreEqual(val1: unknown, val2: unknown): boolean {
  return normalizeValue(val1) === normalizeValue(val2);
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

  const isAdjectiveTable = columns === ADJ_COLUMNS;
  const isNounTable =
    columns === NOUN_COLUMNS || columns === SIMPLE_NOUN_COLUMNS;

  const rowSpanMap: Map<string, number> = new Map();
  const skipCells: Set<string> = new Set();

  if (isNounTable) {
    visibleColumns.forEach(({ suffix: colSuffix }) => {
      for (let i = 0; i < cases.length; i++) {
        const cellKey = `${i}-${colSuffix}`;
        if (skipCells.has(cellKey)) continue;

        const caseKey = cases[i].key;
        const currentValue = forms[`${caseKey} ${colSuffix}`];
        let rowSpan = 1;

        for (let j = i + 1; j < cases.length; j++) {
          const nextCaseKey = cases[j].key;
          const nextValue = forms[`${nextCaseKey} ${colSuffix}`];

          if (
            valuesAreEqual(currentValue, nextValue) &&
            hasFormValue(currentValue)
          ) {
            rowSpan++;
            skipCells.add(`${j}-${colSuffix}`);
          } else {
            break;
          }
        }

        if (rowSpan > 1) {
          rowSpanMap.set(cellKey, rowSpan);
        }
      }
    });
  }

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
        {cases.map(
          (
            { key: caseKey, label: caseLabel, tooltip: caseTooltip },
            rowIdx,
          ) => {
            const cellsToRender: Array<{
              suffix: string;
              colSpan: number;
              rowSpan: number;
              skip: boolean;
            }> = [];

            for (let i = 0; i < visibleColumns.length; i++) {
              const currentSuffix = visibleColumns[i].suffix;
              const cellKey = `${rowIdx}-${currentSuffix}`;

              if (isNounTable && skipCells.has(cellKey)) {
                cellsToRender[i] = {
                  suffix: currentSuffix,
                  colSpan: 1,
                  rowSpan: 1,
                  skip: true,
                };
                continue;
              }

              if (cellsToRender[i]?.skip) {
                continue;
              }

              const currentValue = forms[`${caseKey} ${currentSuffix}`];
              let colSpan = 1;
              let rowSpan = 1;

              if (isNounTable) {
                rowSpan = rowSpanMap.get(cellKey) || 1;
              } else if (isAdjectiveTable) {
                for (let j = i + 1; j < visibleColumns.length; j++) {
                  const nextSuffix = visibleColumns[j].suffix;
                  const nextValue = forms[`${caseKey} ${nextSuffix}`];

                  if (
                    valuesAreEqual(currentValue, nextValue) &&
                    hasFormValue(currentValue)
                  ) {
                    colSpan++;
                    cellsToRender[j] = {
                      suffix: nextSuffix,
                      colSpan: 1,
                      rowSpan: 1,
                      skip: true,
                    };
                  } else {
                    break;
                  }
                }
              }

              cellsToRender[i] = {
                suffix: currentSuffix,
                colSpan,
                rowSpan,
                skip: false,
              };
            }

            return (
              <tr key={caseKey}>
                <th
                  scope="row"
                  className="form-cell-label"
                  data-tooltip-id="table-row-header-tooltip"
                  data-tooltip-content={caseTooltip}
                >
                  {caseLabel}
                </th>
                {cellsToRender.map(
                  ({ suffix, colSpan, rowSpan, skip }, idx) => {
                    if (skip) return null;

                    const rawValue = forms[`${caseKey} ${suffix}`];
                    const val = isFormValue(rawValue) ? rawValue : [];
                    return (
                      <FormCell
                        key={`${suffix}-${idx}`}
                        value={val}
                        query={query}
                        colSpan={colSpan > 1 ? colSpan : undefined}
                        rowSpan={rowSpan > 1 ? rowSpan : undefined}
                      />
                    );
                  },
                )}
              </tr>
            );
          },
        )}
        {children}
      </tbody>
    </table>
  );
};

export default CasesTable;
