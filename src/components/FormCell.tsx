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
  const isEmptyArray = Array.isArray(value) && value.length === 0;
  const isEmptyString = typeof value === 'string' && !value.trim();

  if (isEmptyArray || isEmptyString) {
    return (
      <td data-tooltip={tooltip} colSpan={colSpan}>
        <span className="empty-cell">–</span>
      </td>
    );
  }

  return <NonEmptyFormCell {...props} />;
};

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
    <td className={cellClass} data-tooltip={tooltip} colSpan={colSpan}>
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
