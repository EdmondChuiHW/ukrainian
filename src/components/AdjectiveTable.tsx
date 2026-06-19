import React from 'react';
import FormCell from './FormCell';
import MatchAndStressText from './MatchAndStressText';
import { humanizeKey } from './utils';
import type { AdjectiveForms } from '../types/words';

const CATEGORIES = [
  { key: 'am', label: 'Male' },
  { key: 'an', label: 'Neut.' },
  { key: 'af', label: 'Fem.' },
  { key: 'ap', label: 'Plur.' },
];

const CASE_ROWS = [
  { key: 'nom', label: 'Nom.' },
  { key: 'acc', label: 'Acc.' },
  { key: 'gen', label: 'Gen.' },
  { key: 'dat', label: 'Dat.' },
  { key: 'ins', label: 'Ins.' },
  { key: 'loc', label: 'Loc.' },
];

const TOOLTIPS: { [key: string]: string } = {
  am: 'Male/Чоловічий',
  an: 'Neuter/Середній',
  af: 'Female/Жіночий',
  ap: 'Plural/Множина',
  nom: 'Nominative/Називний — what/who?',
  acc: 'Accusative/Знахідний — what/whom?',
  gen: 'Genitive/Родовий — of what/whom?',
  dat: 'Dative/Давальний — to/for what/whom?',
  ins: 'Instrumental/Орудний — by/with what/whom?',
  loc: 'Locative/Місцевий — in/on what/whom?',
  comp: 'Comparative/Вищий ступінь',
  super: 'Superlative/Найвищий ступінь',
};

interface AdjectiveTableProps {
  forms: AdjectiveForms;
  query: string;
}

export const AdjectiveTable: React.FC<AdjectiveTableProps> = ({
  forms,
  query,
}) => {
  return (
    <table className="form-table">
      <thead>
        <tr className="table-header">
          <th></th>
          {CATEGORIES.map(({ key, label }) => (
            <th
              key={key}
              data-tooltip-id="table-row-header-tooltip"
              data-tooltip-content={TOOLTIPS[key]}
            >
              {label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {CASE_ROWS.map(({ key: caseKey, label: caseLabel }) => (
          <tr key={caseKey}>
            <th
              scope="row"
              className="form-cell-label"
              data-tooltip-id="table-row-header-tooltip"
              data-tooltip-content={TOOLTIPS[caseKey]}
            >
              {caseLabel}
            </th>
            {CATEGORIES.map(({ key: suffix }) => {
              const rawValue = forms[`${caseKey} ${suffix}`];
              const val =
                typeof rawValue === 'string' || Array.isArray(rawValue)
                  ? rawValue
                  : [];
              return <FormCell key={suffix} value={val} query={query} />;
            })}
          </tr>
        ))}

        {forms.addl &&
          Object.entries(forms.addl).map(([addlKey, addlValue]) => (
            <tr key={addlKey}>
              <th
                scope="row"
                className="form-cell-label"
                data-tooltip-id="table-row-header-tooltip"
                data-tooltip-content={TOOLTIPS[addlKey]}
              >
                {humanizeKey(addlKey)}
              </th>
              <td colSpan={4}>
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
      </tbody>
    </table>
  );
};

export default AdjectiveTable;
