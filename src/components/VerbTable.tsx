import React from 'react';
import FormCell from './FormCell';
import { getCellText, humanizeKey } from './utils';

const TOOLTIPS: { [key: string]: string } = {
  inf: 'Infinitive/Інфінітив',
  past: 'Past Tense/Минулий час',
  pres: 'Present Tense/Теперішній час',
  adv: 'Adverbial Participle/Дієприслівник',
  fut: 'Future Tense/Майбутній час',
  imperative: 'Imperative Mood/Наказовий спосіб',
  '1st': '1st Person/Перша особа (я, ми)',
  '2nd': '2nd Person/Друга особа (ти, ви)',
  '3rd': '3rd Person/Третя особа (він, вона, воно, вони)',
  m: 'Male/Чоловічий',
  n: 'Neuter/Середній',
  f: 'Female/Жіночий',
  s: 'Singular/Однина',
  p: 'Plural/Множина',
};

const PRONOUN_MAP: { [tense: string]: { [form: string]: string } } = {
  pres: {
    '1s': 'я',
    '2s': 'ти',
    '3s': 'він/вона/воно',
    '1p': 'ми',
    '2p': 'ви',
    '3p': 'вони',
  },
  fut: {
    '1s': 'я',
    '2s': 'ти',
    '3s': 'він/вона/воно',
    '1p': 'ми',
    '2p': 'ви',
    '3p': 'вони',
  },
  imp: {
    '1p': 'ми',
    '2s': 'ти',
    '2p': 'ви',
  },
  past: {
    ms: 'він',
    ns: 'воно',
    fs: 'вона',
    p: 'вони',
  },
};

import type { RawFormValue } from '../types/words';

type FormValue = string | string[];

type VerbPpForms = Record<string, FormValue>;

type PastForms = {
  ms?: FormValue;
  ns?: FormValue;
  fs?: FormValue;
  p?: FormValue;
  pp?: VerbPpForms;
};

type PresentFutureForms = {
  '1s'?: FormValue;
  '2s'?: FormValue;
  '3s'?: FormValue;
  '1p'?: FormValue;
  '2p'?: FormValue;
  '3p'?: FormValue;
  pp?: VerbPpForms;
};

type ImperativeForms = {
  '1p'?: FormValue;
  '2s'?: FormValue;
  '2p'?: FormValue;
};

export interface VerbForms {
  [key: string]: RawFormValue | undefined;
  inf?: FormValue;
  past?: PastForms;
  pres?: PresentFutureForms;
  fut?: PresentFutureForms;
  imp?: ImperativeForms;
}

const getVerbFormTooltip = (
  tenseKey: string,
  formKey: string,
  value: FormValue | undefined,
): string | undefined => {
  if (!formKey || value == null) return undefined;

  const pronoun = PRONOUN_MAP[tenseKey]?.[formKey];
  if (!pronoun) return undefined;

  const cellValues = Array.isArray(value)
    ? value
    : typeof value === 'string'
      ? [value]
      : [getCellText(value)];

  const text = cellValues
    .filter(Boolean)
    .join(' / ')
    .replaceAll('\u0301', '')
    .trim();

  if (!text) return undefined;

  return `${pronoun} ${text}`;
};

interface VerbTableProps {
  forms: VerbForms;
  query: string;
  showComplexFutureForms?: boolean;
}

const splitFutureFormVariants = (values: string[] = []) => {
  const simpleForms: string[] = [];
  const complexForms: string[] = [];
  // Regex to match future forms that use the auxiliary "буду" (буду, будеш, буде, будемо, будете, будуть) followed by a space.
  // \u0301? allows for an optional combining acute accent on the "у" in "бу́ду".
  const futureAuxiliaryRegex = /^бу\u0301?д(?:у|еш|е|емо|ете|уть)\s/u;

  for (const value of values) {
    // Partition future variants into simple conjugations and auxiliary + infinitive forms.
    // Example: "бу́ду робити" is complex, "робитиму" is simple.
    if (futureAuxiliaryRegex.test(value)) {
      complexForms.push(value);
    } else {
      simpleForms.push(value);
    }
  }

  return { simpleForms, complexForms };
};

const getFutureFormValues = (
  rawValue: FormValue,
  showComplexFutureForms?: boolean,
): { table: FormValue; tooltip: FormValue } => {
  const values = Array.isArray(rawValue) ? rawValue : [rawValue];
  const { simpleForms, complexForms } = splitFutureFormVariants(values);
  const all = [...simpleForms, ...complexForms];

  if (showComplexFutureForms) {
    return { table: all, tooltip: all };
  }

  return { table: simpleForms, tooltip: all };
};

export const VerbTable: React.FC<VerbTableProps> = ({
  forms,
  query,
  showComplexFutureForms = false,
}) => {
  return (
    <table className="form-table">
      <tbody>
        {/* Infinitive Row */}
        {forms.inf && (
          <tr>
            <th
              scope="row"
              className="form-cell-label"
              data-tooltip-id="table-row-header-tooltip"
              data-tooltip-content={TOOLTIPS.inf}
            >
              Inf.
            </th>
            <FormCell value={forms.inf} query={query} colSpan={3} />
          </tr>
        )}

        {/* Past Matrix */}
        {'past' in forms && (
          <>
            <tr className="form-separator">
              <td colSpan={4}></td>
            </tr>
            <tr className="table-header">
              <th
                scope="row"
                className="form-cell-label"
                data-tooltip={TOOLTIPS.past}
              >
                Past
              </th>
              <th
                data-tooltip-id="table-col-header-tooltip"
                data-tooltip-content={TOOLTIPS.m}
              >
                Male
              </th>
              <th
                data-tooltip-id="table-col-header-tooltip"
                data-tooltip-content={TOOLTIPS.n}
              >
                Neuter
              </th>
              <th
                data-tooltip-id="table-col-header-tooltip"
                data-tooltip-content={TOOLTIPS.f}
              >
                Female
              </th>
            </tr>
            <tr>
              <th
                scope="row"
                className="form-cell-label"
                data-tooltip-id="table-row-header-tooltip"
                data-tooltip-content={TOOLTIPS.s}
              >
                Sing.
              </th>
              {(['ms', 'ns', 'fs'] as const).map((key) => {
                const val = forms.past?.[key] || [];
                return (
                  <FormCell
                    key={key}
                    value={val}
                    tooltip={getVerbFormTooltip('past', key, val)}
                    query={query}
                  />
                );
              })}
            </tr>
            <tr>
              <th
                scope="row"
                className="form-cell-label"
                data-tooltip-id="table-row-header-tooltip"
                data-tooltip-content={TOOLTIPS.p}
              >
                Plur.
              </th>
              <FormCell
                value={forms.past?.p || []}
                tooltip={getVerbFormTooltip('past', 'p', forms.past?.p || [])}
                query={query}
                colSpan={3}
              />
            </tr>
            {forms.past?.pp &&
              Object.entries(forms.past.pp).map(([ppKey, ppValue]) => (
                <tr key={ppKey}>
                  <th
                    scope="row"
                    className="form-cell-label"
                    data-tooltip-id="table-row-header-tooltip"
                    data-tooltip-content={TOOLTIPS[ppKey]}
                  >
                    {humanizeKey(ppKey)}
                  </th>
                  <FormCell
                    value={ppValue}
                    tooltip={getVerbFormTooltip('past', ppKey, ppValue)}
                    query={query}
                    colSpan={3}
                  />
                </tr>
              ))}
          </>
        )}

        {/* Present Matrix */}
        {'pres' in forms && (
          <>
            <tr className="form-separator">
              <td colSpan={4}></td>
            </tr>
            <tr className="table-header">
              <th
                scope="row"
                className="form-cell-label"
                data-tooltip-id="table-row-header-tooltip"
                data-tooltip-content={TOOLTIPS.pres}
              >
                Pres.
              </th>
              <th
                data-tooltip-id="table-col-header-tooltip"
                data-tooltip-content={TOOLTIPS['1st']}
              >
                1st
              </th>
              <th
                data-tooltip-id="table-col-header-tooltip"
                data-tooltip-content={TOOLTIPS['2nd']}
              >
                2nd
              </th>
              <th
                data-tooltip-id="table-col-header-tooltip"
                data-tooltip-content={TOOLTIPS['3rd']}
              >
                3rd
              </th>
            </tr>
            <tr>
              <th
                scope="row"
                className="form-cell-label"
                data-tooltip-id="table-row-header-tooltip"
                data-tooltip-content={TOOLTIPS.s}
              >
                Sing.
              </th>
              {(['1s', '2s', '3s'] as const).map((key) => {
                const val = forms.pres?.[key] || [];
                return (
                  <FormCell
                    key={key}
                    value={val}
                    tooltip={getVerbFormTooltip('pres', key, val)}
                    query={query}
                  />
                );
              })}
            </tr>
            <tr>
              <th
                scope="row"
                className="form-cell-label"
                data-tooltip-id="table-row-header-tooltip"
                data-tooltip-content={TOOLTIPS.p}
              >
                Plur.
              </th>
              {(['1p', '2p', '3p'] as const).map((key) => {
                const val = forms.pres?.[key] || [];
                return (
                  <FormCell
                    key={key}
                    value={val}
                    tooltip={getVerbFormTooltip('pres', key, val)}
                    query={query}
                  />
                );
              })}
            </tr>
            {forms.pres?.pp &&
              Object.entries(forms.pres.pp).map(([ppKey, ppValue]) => (
                <tr key={ppKey}>
                  <th
                    scope="row"
                    className="form-cell-label"
                    data-tooltip-id="table-row-header-tooltip"
                    data-tooltip-content={TOOLTIPS[ppKey]}
                  >
                    {humanizeKey(ppKey)}
                  </th>
                  <FormCell
                    value={ppValue}
                    tooltip={getVerbFormTooltip('pres', ppKey, ppValue)}
                    query={query}
                    colSpan={3}
                  />
                </tr>
              ))}
          </>
        )}

        {/* Future Matrix */}
        {'fut' in forms && (
          <>
            <tr className="form-separator">
              <td colSpan={4}></td>
            </tr>
            <tr className="table-header">
              <th
                scope="row"
                className="form-cell-label"
                data-tooltip-id="table-row-header-tooltip"
                data-tooltip-content={TOOLTIPS.fut}
              >
                Fut.
              </th>
              <th
                data-tooltip-id="table-col-header-tooltip"
                data-tooltip-content={TOOLTIPS['1st']}
              >
                1st
              </th>
              <th
                data-tooltip-id="table-col-header-tooltip"
                data-tooltip-content={TOOLTIPS['2nd']}
              >
                2nd
              </th>
              <th
                data-tooltip-id="table-col-header-tooltip"
                data-tooltip-content={TOOLTIPS['3rd']}
              >
                3rd
              </th>
            </tr>
            <tr>
              <th
                scope="row"
                className="form-cell-label"
                data-tooltip-id="table-row-header-tooltip"
                data-tooltip-content={TOOLTIPS.s}
              >
                Sing.
              </th>
              {(['1s', '2s', '3s'] as const).map((key) => {
                const rawValue = forms.fut?.[key] || [];
                const { table, tooltip } = getFutureFormValues(
                  rawValue,
                  showComplexFutureForms,
                );

                return (
                  <FormCell
                    key={key}
                    value={table}
                    tooltip={getVerbFormTooltip('fut', key, tooltip)}
                    query={query}
                  />
                );
              })}
            </tr>
            <tr>
              <th
                scope="row"
                className="form-cell-label"
                data-tooltip-id="table-row-header-tooltip"
                data-tooltip-content={TOOLTIPS.p}
              >
                Plur.
              </th>
              {(['1p', '2p', '3p'] as const).map((key) => {
                const rawValue = forms.fut?.[key] || [];
                const { table, tooltip } = getFutureFormValues(
                  rawValue,
                  showComplexFutureForms,
                );

                return (
                  <FormCell
                    key={key}
                    value={table}
                    tooltip={getVerbFormTooltip('fut', key, tooltip)}
                    query={query}
                  />
                );
              })}
            </tr>
            {forms.fut?.pp &&
              Object.entries(forms.fut.pp).map(([ppKey, ppValue]) => (
                <tr key={ppKey}>
                  <th
                    scope="row"
                    className="form-cell-label"
                    data-tooltip-id="table-row-header-tooltip"
                    data-tooltip-content={TOOLTIPS[ppKey]}
                  >
                    {humanizeKey(ppKey)}
                  </th>
                  <FormCell
                    value={ppValue}
                    tooltip={getVerbFormTooltip('fut', ppKey, ppValue)}
                    query={query}
                    colSpan={3}
                  />
                </tr>
              ))}
          </>
        )}

        {/* Imperative Matrix */}
        {'imp' in forms && (
          <>
            <tr className="form-separator">
              <td colSpan={4}></td>
            </tr>
            <tr className="table-header">
              <th
                scope="row"
                className="form-cell-label"
                data-tooltip-id="table-row-header-tooltip"
                data-tooltip-content={TOOLTIPS.imperative}
              >
                Imp.
              </th>
              <th
                data-tooltip-id="table-col-header-tooltip"
                data-tooltip-content={TOOLTIPS['1st']}
              >
                1st
              </th>
              <th
                data-tooltip-id="table-col-header-tooltip"
                data-tooltip-content={TOOLTIPS['2nd']}
              >
                2nd
              </th>
              {/* <th></th> */}
            </tr>
            <tr>
              <th
                scope="row"
                className="form-cell-label"
                data-tooltip-id="table-row-header-tooltip"
                data-tooltip-content={TOOLTIPS.s}
              >
                Sing.
              </th>
              <td>
                <span className="empty-cell">–</span>
              </td>
              <FormCell
                value={forms.imp?.['2s'] || []}
                tooltip={getVerbFormTooltip(
                  'imp',
                  '2s',
                  forms.imp?.['2s'] || [],
                )}
                query={query}
              />
              {/* <td></td> */}
            </tr>
            <tr>
              <th
                scope="row"
                className="form-cell-label"
                data-tooltip-id="table-row-header-tooltip"
                data-tooltip-content={TOOLTIPS.p}
              >
                Plur.
              </th>
              <FormCell
                value={forms.imp?.['1p'] || []}
                tooltip={getVerbFormTooltip(
                  'imp',
                  '1p',
                  forms.imp?.['1p'] || [],
                )}
                query={query}
              />
              <FormCell
                value={forms.imp?.['2p'] || []}
                tooltip={getVerbFormTooltip(
                  'imp',
                  '2p',
                  forms.imp?.['2p'] || [],
                )}
                query={query}
              />
              {/* <td></td> */}
            </tr>
          </>
        )}
      </tbody>
    </table>
  );
};

export default VerbTable;
