import React from 'react';
import MatchAndStressText from './MatchAndStressText';
import { humanizeKey } from './utils';

interface GenericFormsProps {
  forms: any;
  query: string;
}

export const FormValue: React.FC<{ value: any; query: string }> = ({
  value,
  query,
}) => {
  if (Array.isArray(value)) {
    return (
      <div className="form-values">
        {value.map((item, idx) => (
          <p key={idx}>
            <MatchAndStressText text={item} matchTerm={query} />
          </p>
        ))}
      </div>
    );
  }

  if (value && typeof value === 'object') {
    return (
      <div className="form-nested">
        {Object.entries(value).map(([subKey, subValue]) => (
          <div key={subKey} className="form-row">
            <span className="form-label-inline">{humanizeKey(subKey)}</span>
            <FormValue value={subValue} query={query} />
          </div>
        ))}
      </div>
    );
  }

  return (
    <p>
      <MatchAndStressText text={value ?? ''} matchTerm={query} />
    </p>
  );
};

export const GenericForms: React.FC<GenericFormsProps> = ({ forms, query }) => {
  return (
    <div className="form-group">
      {Object.entries(forms).map(([key, value]) => (
        <div key={key} className="form-row">
          <span className="form-label-inline">{humanizeKey(key)}</span>
          <FormValue value={value} query={query} />
        </div>
      ))}
    </div>
  );
};

export default GenericForms;
