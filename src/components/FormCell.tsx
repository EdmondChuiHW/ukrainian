import React from 'react';
import MatchAndStressText from './MatchAndStressText';
import { hasExactCellMatch } from './utils';
import type { FormValue } from '../types/words';

interface FormCellProps {
  value: FormValue;
  query: string;
  tooltip?: string;
  colSpan?: number;
  separator?: string;
}

export const FormCell: React.FC<FormCellProps> = (props) => {
  const { value, tooltip, colSpan } = props;
  if (isEmpty(value)) {
    return (
      <td
        data-tooltip-id="table-cell-tooltip"
        data-tooltip-content={tooltip}
        colSpan={colSpan}
      >
        <span className="empty-cell">–</span>
      </td>
    );
  }

  return <NonEmptyFormCell {...props} />;
};

function isEmpty(value: unknown) {
  const isEmptyArray = Array.isArray(value) && value.length === 0;
  if (isEmptyArray) return true;

  const isEmptyStringFn = (v: unknown) => typeof v === 'string' && !v.trim();

  const isEmptyString = isEmptyStringFn(value);
  if (isEmptyString) return true;

  const isAllEmptyArray = Array.isArray(value) && value.every(isEmptyStringFn);
  if (isAllEmptyArray) return true;

  return false;
}

export const NonEmptyFormCell: React.FC<FormCellProps> = ({
  value,
  tooltip,
  query,
  colSpan,
  separator: separatorProp,
}) => {
  const separator = separatorProp ?? (colSpan && colSpan > 1 ? ', ' : <br />);
  const isExact = hasExactCellMatch(value, query);
  const cellClass = isExact ? 'cell-exact' : undefined;

  return (
    <td
      className={cellClass}
      data-tooltip-id="table-cell-tooltip"
      data-tooltip-content={tooltip}
      colSpan={colSpan}
    >
      {Array.isArray(value) ? (
        value.map((item, idx) => (
          <React.Fragment key={`cell-item-${idx}`}>
            <MatchAndStressText text={item} matchTerm={query} />
            {idx < value.length - 1 && <>{separator}</>}
          </React.Fragment>
        ))
      ) : (
        <MatchAndStressText text={value} matchTerm={query} />
      )}
    </td>
  );
};

export default FormCell;
