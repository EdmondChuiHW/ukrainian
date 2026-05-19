import React, { useState, useEffect, useRef, useTransition } from 'react';
import { useQueryState } from 'nuqs';

interface SearchBarProps {
  onSearchChange: (value: string) => void;
}

export const SearchBar: React.FC<SearchBarProps> = ({ onSearchChange }) => {
  const [q] = useQueryState('q', { defaultValue: '' });
  const [localVal, setLocalVal] = useState(q);
  const [, startTransition] = useTransition();
  const inputRef = useRef<HTMLInputElement>(null);

  // Sync internal input value with external query state (e.g. from counterpart clicks)
  useEffect(() => {
    setLocalVal(q);
  }, [q]);

  const updateSearch = (val: string) => {
    setLocalVal(val);
    startTransition(() => {
      onSearchChange(val);
    });
  };

  const handleClear = () => {
    updateSearch('');
    inputRef.current?.focus();
  };

  const handlePaste = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        updateSearch(text);
        inputRef.current?.focus();
      }
    } catch (err) {
      console.error('Failed to read clipboard contents:', err);
    }
  };

  return (
    <div className="toolbar" role="search" aria-label="Dictionary search">
      <div className="toolbar-field">
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
          <input
            ref={inputRef}
            id="search"
            type="search"
            placeholder="Search for Ukrainian words or definitions..."
            value={localVal}
            onChange={(e) => updateSearch(e.target.value)}
            autoComplete="off"
            autoCorrect="off"
            autoCapitalize="off"
            spellCheck="false"
            aria-label="Search dictionary"
          />
        </div>
      </div>

      <div className="toolbar-actions">
        {localVal && (
          <button
            id="clearSearch"
            type="button"
            onClick={handleClear}
            className="button button--secondary"
            aria-label="Clear search"
          >
            Clear
          </button>
        )}
        <button
          id="pasteSearch"
          type="button"
          onClick={handlePaste}
          className="button button--primary"
          aria-label="Paste from clipboard"
        >
          Paste
        </button>
      </div>
    </div>
  );
};

export default SearchBar;
