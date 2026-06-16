import React, { useRef } from 'react';
import { debounce, useQueryState } from 'nuqs';

export const SearchBar: React.FC = () => {
  const [q, setQuery] = useQueryState('q', { defaultValue: '' });
  const inputRef = useRef<HTMLInputElement>(null);

  const handleClear = () => {
    void setQuery('');
    inputRef.current?.focus();
  };

  const handlePaste = async () => {
    let text = null;
    try {
      text = await navigator.clipboard.readText();
    } catch (err) {
      console.error('Failed to read clipboard contents:', err);
    }
    if (!text) return;

    void setQuery(text);
    inputRef.current?.focus();
  };

  return (
    <div className="toolbar" role="search" aria-label="Dictionary search">
      <div className="toolbar-field">
        <div
          style={{
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
          }}
        >
          <input
            ref={inputRef}
            id="search"
            type="search"
            placeholder="Search for Ukrainian words or definitions…"
            value={q}
            onChange={(e) =>
              void setQuery(e.target.value, { limitUrlUpdates: debounce(500) })
            }
            autoComplete="off"
            autoCorrect="off"
            autoCapitalize="off"
            spellCheck="false"
            aria-label="Search dictionary"
          />
        </div>
      </div>

      <div className="toolbar-actions">
        {q && (
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
          // eslint-disable-next-line @typescript-eslint/no-misused-promises
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
