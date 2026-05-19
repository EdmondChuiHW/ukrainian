import React, { Fragment } from 'react';

interface StressTextProps {
  text: string;
}

const ACCENT_MARK = '\u0301';

export const StressText: React.FC<StressTextProps> = ({ text }) => {
  if (!text) return null;

  const elements: React.ReactNode[] = [];

  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    const isStressed = text[i + 1] === ACCENT_MARK;

    if (isStressed) {
      elements.push(
        <span key={i} className="stress">
          {char}
        </span>,
      );
      i++; // skip the accent mark
    } else if (char !== ACCENT_MARK) {
      elements.push(<Fragment key={i}>{char}</Fragment>);
    }
  }

  return <>{elements}</>;
};

StressText.displayName = 'StressText';

export default StressText;
