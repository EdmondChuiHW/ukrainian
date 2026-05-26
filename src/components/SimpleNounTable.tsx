import React from 'react';
import FormCell from './FormCell';

const CASE_LABELS: { [key: string]: string } = {
  nom: 'Nom.',
  acc: 'Acc.',
  gen: 'Gen.',
  dat: 'Dat.',
  ins: 'Ins.',
  loc: 'Loc.',
  voc: 'Voc.',
};

const TOOLTIPS: { [key: string]: string } = {
  nom: 'Nominative/Називний — what/who?',
  acc: 'Accusative/Знахідний — what/whom?',
  gen: 'Genitive/Родовий — of what/whom?',
  dat: 'Dative/Давальний — to/for what/whom?',
  ins: 'Instrumental/Орудний — by/with what/whom?',
  loc: 'Locative/Місцевий — in/on what/whom?',
  voc: 'Vocative/Кличний — direct address',
};

type FormValue = string | string[];

interface SimpleNounTableProps {
  forms: Record<string, FormValue>;
  query: string;
}

export const SimpleNounTable: React.FC<SimpleNounTableProps> = ({
  forms,
  query,
}) => {
  return (
    <table className="form-table">
      <tbody>
        {Object.entries(CASE_LABELS).map(([caseKey, caseLabel]) => {
          const formKey = `${caseKey} n`;
          if (!(formKey in forms)) return null;
          const val = forms[formKey];
          return (
            <tr key={caseKey}>
              <th
                scope="row"
                className="form-cell-label"
                data-tooltip={TOOLTIPS[caseKey]}
              >
                {caseLabel}
              </th>
              <FormCell value={val} tooltip={TOOLTIPS[caseKey]} query={query} />
            </tr>
          );
        })}
      </tbody>
    </table>
  );
};

export default SimpleNounTable;
