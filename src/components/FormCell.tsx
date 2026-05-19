import React from 'react';
import HighlightedText from './HighlightedText';
import { hasExactCellMatch } from './utils';

interface FormCellProps {
  value: any;
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
          <HighlightedText text={item} query={query} />
          {idx < value.length - 1 && <br />}
        </React.Fragment>
      ));
    }
    return <HighlightedText text={value} query={query} />;
  };

  return (
    <td className={cellClass} data-tooltip={tooltip}>
      {renderCellContent()}
    </td>
  );
};

export default FormCell;
