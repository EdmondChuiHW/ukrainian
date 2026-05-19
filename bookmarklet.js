// Bookmarklet helper for opening the Ukrainian dictionary popup and sending updates from .reference-word

(function () {
  const targetOrigin = 'http://localhost:8000';
  const getText = (el) => el?.textContent?.trim() || '';
  const initialWord =
    getText(document.querySelector('.reference-word')) || 'раз';
  const popup = window.open(
    `${targetOrigin}/?q=${encodeURIComponent(initialWord)}`,
    'ukrDictPopup',
    'width=940,height=860',
  );
  if (!popup) {
    alert('Popup blocked. Allow popups for this site.');
    return;
  }
  let lastValue = '';
  let currentElement = null;
  let referenceObserver = null;

  const sendQuery = (value) => {
    const text = getText(value);
    if (!text || text === lastValue) return;
    lastValue = text;
    if (popup && !popup.closed) {
      popup.postMessage({ q: text }, targetOrigin);
    }
  };

  const observeReferenceWord = (el) => {
    if (!el || el === currentElement) return;
    if (referenceObserver) {
      referenceObserver.disconnect();
      referenceObserver = null;
    }

    currentElement = el;
    sendQuery(el);

    referenceObserver = new MutationObserver(() => sendQuery(el));
    referenceObserver.observe(el, {
      childList: true,
      characterData: true,
      subtree: true,
    });
    window.addEventListener('beforeunload', () => {
      referenceObserver?.disconnect();
    });
  };

  const init = () => {
    const findAndObserve = () => {
      const found = document.querySelector('.reference-word');
      if (!found) return;
      observeReferenceWord(found);
    };

    const bodyObserver = new MutationObserver(() => {
      if (currentElement && !document.body.contains(currentElement)) {
        currentElement = null;
        referenceObserver?.disconnect();
        referenceObserver = null;
      }
      if (!currentElement) {
        findAndObserve();
      }
    });
    bodyObserver.observe(document.body, { childList: true, subtree: true });

    findAndObserve();
  };

  init();
})();
