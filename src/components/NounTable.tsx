import React from 'react';
import FormCell from './FormCell';

const CASE_LABELS: { [key: string]: string } = {
  nom: "Nom.",
  acc: "Acc.",
  gen: "Gen.",
  dat: "Dat.",
  ins: "Ins.",
  loc: "Loc.",
  voc: "Voc.",
};

const TOOLTIPS: { [key: string]: string } = {
  nom: "Nominative/Називний — what/who?",
  acc: "Accusative/Знахідний — what/whom?",
  gen: "Genitive/Родовий — of what/whom?",
  dat: "Dative/Давальний — to/for what/whom?",
  ins: "Instrumental/Орудний — by/with what/whom?",
  loc: "Locative/Місцевий — in/on what/whom?",
  voc: "Vocative/Кличний — direct address",
  s: "Singular/Однина",
  p: "Plural/Множина",
};

interface NounTableProps {
  forms: any;
  query: string;
}

export const NounTable: React.FC<NounTableProps> = ({ forms, query }) => {
  return (
    <table className="form-table">
      <thead>
        <tr className="table-header">
          <th></th>
          <th data-tooltip={TOOLTIPS.s}>Sing.</th>
          <th data-tooltip={TOOLTIPS.p}>Plur.</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(CASE_LABELS).map(([caseKey, caseLabel]) => {
          const singVal = forms[`${caseKey} ns`] || [];
          const plurVal = forms[`${caseKey} np`] || [];
          return (
            <tr key={caseKey}>
              <th scope="row" className="form-cell-label" data-tooltip={TOOLTIPS[caseKey]}>
                {caseLabel}
              </th>
              <FormCell value={singVal} tooltip={TOOLTIPS[caseKey]} query={query} />
              <FormCell value={plurVal} tooltip={TOOLTIPS[caseKey]} query={query} />
            </tr>
          );
        })}
      </tbody>
    </table>
  );
};

export default NounTable;
