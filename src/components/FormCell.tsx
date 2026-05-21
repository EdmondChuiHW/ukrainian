import React from 'react';
import MatchAndStressText from './MatchAndStressText';
import { hasExactCellMatch } from './utils';

interface FormCellProps {
  value: string | string[];
  tooltip?: string;
  query: string;
}

export const FormCell: React.FC<FormCellProps> = ({
  value,
  tooltip,
  query,
}) => {
  const isEmptyArray = Array.isArray(value) && value.length === 0;
  const isEmptyString = typeof value === 'string' && !value.trim();

  if (value == null || isEmptyArray || isEmptyString) {
    return (
      <td data-tooltip={tooltip}>
        <span className="empty-cell">–</span>
      </td>
    );
  }

  const isExact = hasExactCellMatch(value, query);
  const cellClass = isExact ? 'cell-exact' : undefined;

  const renderCellContent = () => {
    if (Array.isArray(value)) {
      return value.map((item, idx) => (
        <React.Fragment key={`cell-item-${idx}`}>
          <MatchAndStressText text={item} matchTerm={query} />
          {idx < value.length - 1 && <br />}
        </React.Fragment>
      ));
    }
    return <MatchAndStressText text={value} matchTerm={query} />;
  };

  return (
    <td className={cellClass} data-tooltip={tooltip}>
      {renderCellContent()}
    </td>
  );
};

export default FormCell;
