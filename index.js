"use strict";

const RESULTS_PER_PAGE = 50;
const ACCENT_MARK = "\u0301";

let words = [];
let filteredWords = [];
let sortInfo = "freq";
let curFilter = "";
let searchTerm = "";
let currentPage = 1;

const searchInput = document.getElementById("search");
const sortSelect = document.getElementById("sort");
const filterSelect = document.getElementById("filter");
const resultCount = document.getElementById("resultCount");
const dictionaryList = document.querySelector(".dictionary-list");
const clearButton = document.getElementById("clear");
const pasteButton = document.getElementById("paste");

const debounce = (fn, delay = 250) => {
  let timeoutId;
  return (...args) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn(...args), delay);
  };
};

const normalizeText = (text = "") => {
  return text
    .toString()
    .toLowerCase()
    .replaceAll(ACCENT_MARK, "")
    .replaceAll("ї", "і")
    .replaceAll("ґ", "г")
    .replaceAll(/[“”«»„]/g, '"')
    .replaceAll(/[‘’‚‛‹›]/g, "'")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9а-яєіїґ'\s-]+/gi, " ")
    .replace(/\s+/g, " ")
    .trim();
};

const buildWiktionaryUrl = (word = "") => {
  const normalizedWord = word.toString().replaceAll(ACCENT_MARK, "").trim();
  return `https://en.wiktionary.org/wiki/${encodeURIComponent(normalizedWord)}#Ukrainian`;
};

const buildWiktionaryLink = (
  word = "",
  text = "View on Wiktionary",
  className = "wiktionary-link",
) => {
  const link = document.createElement("a");
  link.className = className;
  link.href = buildWiktionaryUrl(word);
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = text;
  return link;
};

const extractText = (value) => {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(extractText).join(" ");
  if (value && typeof value === "object")
    return Object.values(value).map(extractText).join(" ");
  return "";
};

const buildIndex = (entry) => {
  return {
    ...entry,
    normalizedWord: normalizeText(entry.word),
    normalizedDefs: normalizeText(entry.defs?.join(" ") ?? ""),
    normalizedForms: normalizeText(extractText(entry.forms)),
  };
};

const humanizeKey = (key) => {
  const alias = {
    addl: "Additional forms",
    comp: "Comparative",
    super: "Superlative",
    arg: "Argumentative",
    adv: "Adv. Part.",
    imp: "Imp. Part.",
    act: "Act. Part.",
    pas: "Pass. Part.",
    m: "Male",
    n: "Neuter",
    f: "Female",
    s: "Sing.",
    p: "Plur.",
  };
  if (alias[key]) return alias[key];
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase())
    .replace(/\s+/g, " ");
};

const renderStressText = (text) => {
  const fragment = document.createDocumentFragment();
  let buffer = "";

  for (const char of text) {
    if (char === ACCENT_MARK) {
      if (!buffer) continue;
      const lastChar = buffer.slice(-1);
      const prefix = buffer.slice(0, -1);
      if (prefix) fragment.appendChild(document.createTextNode(prefix));
      const stressSpan = document.createElement("span");
      stressSpan.className = "stress";
      stressSpan.textContent = lastChar;
      fragment.appendChild(stressSpan);
      buffer = "";
      continue;
    }
    buffer += char;
  }

  if (buffer) fragment.appendChild(document.createTextNode(buffer));
  return fragment;
};

const normalizeCharForHighlight = (char) => {
  const smartQuoteMap = {
    "“": '"',
    "”": '"',
    "«": '"',
    "»": '"',
    "„": '"',
    "‘": "'",
    "’": "'",
    "‚": "'",
    "‛": "'",
    "‹": "'",
    "›": "'",
  };
  if (char === ACCENT_MARK) return null;
  if (smartQuoteMap[char]) return smartQuoteMap[char];
  const lower = char.toLowerCase();
  if (lower === "ї") return "і";
  if (lower === "ґ") return "г";
  if (/[a-z0-9а-яєіїґ]/i.test(lower)) return lower;
  if (/['\s-]/.test(lower)) return lower;
  return " ";
};

const renderHighlightText = (text, query) => {
  if (typeof text !== "string") return document.createTextNode(text ?? "");
  const normalizedQuery = normalizeText(query || "");
  if (!normalizedQuery) {
    return renderStressText(text);
  }

  const segments = [];
  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    if (char === ACCENT_MARK) continue;
    let original = char;
    if (i + 1 < text.length && text[i + 1] === ACCENT_MARK) {
      original = char + text[i + 1];
      i += 1;
    }
    const norm = normalizeCharForHighlight(char);
    segments.push({ original, norm });
  }

  const normalizedText = segments
    .map((segment) => segment.norm || " ")
    .join("");
  const ranges = [];
  let index = 0;
  while (index < normalizedText.length) {
    const found = normalizedText.indexOf(normalizedQuery, index);
    if (found === -1) break;
    ranges.push([found, found + normalizedQuery.length]);
    index = found + Math.max(1, normalizedQuery.length);
  }

  if (!ranges.length) {
    return renderStressText(text);
  }

  const mergedRanges = [];
  for (const range of ranges) {
    if (
      !mergedRanges.length ||
      range[0] > mergedRanges[mergedRanges.length - 1][1]
    ) {
      mergedRanges.push(range);
    } else {
      mergedRanges[mergedRanges.length - 1][1] = Math.max(
        mergedRanges[mergedRanges.length - 1][1],
        range[1],
      );
    }
  }

  const fragment = document.createDocumentFragment();
  let nextSegment = 0;
  mergedRanges.forEach(([start, end]) => {
    while (nextSegment < start) {
      fragment.appendChild(renderStressText(segments[nextSegment].original));
      nextSegment += 1;
    }
    const highlight = document.createElement("mark");
    highlight.className = "match";
    for (let i = start; i < end; i += 1) {
      highlight.appendChild(renderStressText(segments[i].original));
    }
    fragment.appendChild(highlight);
    nextSegment = end;
  });

  while (nextSegment < segments.length) {
    fragment.appendChild(renderStressText(segments[nextSegment].original));
    nextSegment += 1;
  }

  return fragment;
};

const renderText = (text) => renderHighlightText(text, searchTerm);

const createListHeader = () => {
  const header = document.createElement("div");
  header.className = "list-header";
  const wordLabel = document.createElement("span");
  wordLabel.className = "list-column list-column--word";
  wordLabel.textContent = "Word";
  const formsLabel = document.createElement("span");
  formsLabel.className = "list-column list-column--forms";
  formsLabel.textContent = "Forms / Declensions";
  header.appendChild(wordLabel);
  header.appendChild(formsLabel);
  return header;
};

const createFormValue = (value) => {
  if (Array.isArray(value)) {
    const wrapper = document.createElement("div");
    wrapper.className = "form-values";
    value.forEach((item) => {
      const itemLine = document.createElement("p");
      itemLine.appendChild(renderText(item));
      wrapper.appendChild(itemLine);
    });
    return wrapper;
  }

  if (value && typeof value === "object") {
    const wrapper = document.createElement("div");
    wrapper.className = "form-nested";
    Object.entries(value).forEach(([subKey, subValue]) => {
      const row = document.createElement("div");
      row.className = "form-row";
      const label = document.createElement("span");
      label.className = "form-label-inline";
      label.textContent = humanizeKey(subKey);
      row.appendChild(label);
      row.appendChild(createFormValue(subValue));
      wrapper.appendChild(row);
    });
    return wrapper;
  }

  const paragraph = document.createElement("p");
  paragraph.appendChild(renderText(value ?? ""));
  return paragraph;
};

const appendFormattedText = (container, value) => {
  if (Array.isArray(value)) {
    value.forEach((item, index) => {
      container.appendChild(renderText(item));
      if (index < value.length - 1)
        container.appendChild(document.createElement("br"));
    });
    return;
  }
  container.appendChild(renderText(value ?? ""));
};

const caseLabels = {
  nom: "Nom.",
  acc: "Acc.",
  gen: "Gen.",
  dat: "Dat.",
  ins: "Ins.",
  loc: "Loc.",
  voc: "Voc.",
};

const isSimpleNounForms = (forms) => {
  const keys = Object.keys(forms);
  if (!keys.length) return false;
  return keys.every((key) => /^(nom|acc|gen|dat|ins|loc|voc) n$/.test(key));
};

const isNounForms = (forms) => {
  const keys = Object.keys(forms);
  if (!keys.length) return false;
  return keys.every((key) =>
    /^(nom|acc|gen|dat|ins|loc|voc) (ns|np)$/.test(key),
  );
};

const isAdjectiveForms = (forms) => {
  const keys = Object.keys(forms);
  return keys.some((key) =>
    /^(nom|acc|gen|dat|ins|loc) (am|an|af|ap)$/.test(key),
  );
};

const isVerbForms = (forms) => {
  return ["inf", "pres", "past", "fut", "imp"].some((key) => key in forms);
};

const createTableCell = (value) => {
  const td = document.createElement("td");
  const isEmptyArray = Array.isArray(value) && value.length === 0;
  const isEmptyString = typeof value === "string" && !value.trim();
  if (value == null || isEmptyArray || isEmptyString) {
    const placeholder = document.createElement("span");
    placeholder.className = "empty-cell";
    placeholder.textContent = "–";
    td.appendChild(placeholder);
    return td;
  }

  appendFormattedText(td, value);
  return td;
};

const createHeaderCell = (text, scope = "col") => {
  const th = document.createElement("th");
  if (scope) th.scope = scope;
  th.textContent = text;
  return th;
};

const createRowHeaderCell = (text) => {
  const th = createHeaderCell(text, "row");
  th.className = "form-cell-label";
  return th;
};

const renderSimpleNounTable = (forms) => {
  const table = document.createElement("table");
  table.className = "form-table";
  Object.keys(caseLabels).forEach((key) => {
    if (!(key + " n" in forms)) return;
    const row = table.insertRow();
    const label = row.insertCell();
    label.className = "form-cell-label";
    label.textContent = caseLabels[key];
    row.appendChild(createTableCell(forms[`${key} n`]));
  });
  return table;
};

const renderNounTable = (forms) => {
  const table = document.createElement("table");
  table.className = "form-table";
  const header = table.insertRow();
  header.className = "table-header";
  header.insertCell().textContent = "";
  const singLabel = header.insertCell();
  singLabel.textContent = "Sing.";
  const plurLabel = header.insertCell();
  plurLabel.textContent = "Plur.";

  Object.keys(caseLabels).forEach((key) => {
    const row = table.insertRow();
    const label = row.insertCell();
    label.className = "form-cell-label";
    label.textContent = caseLabels[key];
    row.appendChild(createTableCell(forms[`${key} ns`] || []));
    row.appendChild(createTableCell(forms[`${key} np`] || []));
  });
  return table;
};

const renderAdjectiveTable = (forms) => {
  const categories = [
    ["am", "Male"],
    ["an", "Neut."],
    ["af", "Fem."],
    ["ap", "Plur."],
  ];
  const rows = [
    ["nom", "Nom."],
    ["acc", "Acc."],
    ["gen", "Gen."],
    ["dat", "Dat."],
    ["ins", "Ins."],
    ["loc", "Loc."],
  ];
  const table = document.createElement("table");
  table.className = "form-table";
  const header = table.insertRow();
  header.className = "table-header";
  header.insertCell().textContent = "";
  categories.forEach(([, label]) => {
    const cell = header.insertCell();
    cell.textContent = label;
  });

  rows.forEach(([caseKey, caseLabel]) => {
    const row = table.insertRow();
    const labelCell = row.insertCell();
    labelCell.className = "form-cell-label";
    labelCell.textContent = caseLabel;
    categories.forEach(([suffix]) => {
      row.appendChild(createTableCell(forms[`${caseKey} ${suffix}`] || []));
    });
  });

  if ("addl" in forms) {
    Object.entries(forms.addl).forEach(([addlKey, addlValue]) => {
      const row = table.insertRow();
      const labelCell = row.insertCell();
      labelCell.className = "form-cell-label";
      labelCell.textContent = humanizeKey(addlKey);
      const cell = row.insertCell();
      cell.colSpan = 4;
      appendFormattedText(cell, addlValue);
    });
  }

  return table;
};

const renderVerbTable = (forms) => {
  const table = document.createElement("table");
  table.className = "form-table";

  const addInf = () => {
    if (!forms.inf) return;
    const row = table.insertRow();
    const label = row.insertCell();
    label.className = "form-cell-label";
    label.textContent = "Inf.";
    const valueCell = row.insertCell();
    valueCell.colSpan = 4;
    appendFormattedText(valueCell, forms.inf);
  };

  addInf();

  const renderTenseMatrix = (tenseKey, tenseLabel, headers, rowKeys) => {
    const headerRow = table.insertRow();
    headerRow.appendChild(createRowHeaderCell(tenseLabel));
    headers.forEach((headerText) => {
      headerRow.appendChild(createHeaderCell(headerText));
    });

    rowKeys.forEach(([rowLabel, formKeys]) => {
      const row = table.insertRow();
      row.appendChild(createRowHeaderCell(rowLabel));
      formKeys.forEach((formKey) => {
        row.appendChild(
          createTableCell(formKey ? forms[tenseKey][formKey] || [] : []),
        );
      });
    });

    if (forms[tenseKey].pp) {
      Object.entries(forms[tenseKey].pp).forEach(([ppKey, ppValue]) => {
        const row = table.insertRow();
        row.appendChild(createRowHeaderCell(humanizeKey(ppKey)));
        const cell = row.insertCell();
        cell.colSpan = headers.length;
        appendFormattedText(cell, ppValue);
      });
    }
  };

  const renderPastMatrix = () => {
    const headerRow = table.insertRow();
    headerRow.appendChild(createRowHeaderCell("Past"));
    ["Male", "Neuter", "Fem."].forEach((headerText) => {
      headerRow.appendChild(createHeaderCell(headerText));
    });

    const singRow = table.insertRow();
    singRow.appendChild(createRowHeaderCell("Sing."));
    ["ms", "ns", "fs"].forEach((formKey) => {
      singRow.appendChild(createTableCell(forms.past[formKey] || []));
    });

    const plurRow = table.insertRow();
    plurRow.appendChild(createRowHeaderCell("Plur."));
    const pluralCell = createTableCell(forms.past.p || []);
    pluralCell.colSpan = 3;
    plurRow.appendChild(pluralCell);

    if (forms.past.pp) {
      Object.entries(forms.past.pp).forEach(([ppKey, ppValue]) => {
        const row = table.insertRow();
        row.appendChild(createRowHeaderCell(humanizeKey(ppKey)));
        const cell = row.insertCell();
        cell.colSpan = 3;
        appendFormattedText(cell, ppValue);
      });
    }
  };

  if ("past" in forms) {
    renderPastMatrix();
  }

  if ("pres" in forms) {
    renderTenseMatrix(
      "pres",
      "Pres.",
      ["1st", "2nd", "3rd"],
      [
        ["Sing.", ["1s", "2s", "3s"]],
        ["Plur.", ["1p", "2p", "3p"]],
      ],
    );
  }

  if ("fut" in forms) {
    renderTenseMatrix(
      "fut",
      "Fut.",
      ["1st", "2nd", "3rd"],
      [
        ["Sing.", ["1s", "2s", "3s"]],
        ["Plur.", ["1p", "2p", "3p"]],
      ],
    );
  }

  if ("imp" in forms) {
    const headerRow = table.insertRow();
    headerRow.appendChild(createRowHeaderCell("Imp."));
    ["1st", "2nd"].forEach((headerText) => {
      headerRow.appendChild(createHeaderCell(headerText));
    });

    const singularRow = table.insertRow();
    singularRow.appendChild(createRowHeaderCell("Sing."));
    singularRow.appendChild(createTableCell([]));
    singularRow.appendChild(createTableCell(forms.imp["2s"] || []));

    const pluralRow = table.insertRow();
    pluralRow.appendChild(createRowHeaderCell("Plur."));
    pluralRow.appendChild(createTableCell(forms.imp["1p"] || []));
    pluralRow.appendChild(createTableCell(forms.imp["2p"] || []));
  }

  return table;
};

const renderGenericFormGroup = (forms) => {
  const wrapper = document.createElement("div");
  wrapper.className = "form-group";
  Object.entries(forms).forEach(([key, value]) => {
    const row = document.createElement("div");
    row.className = "form-row";
    const label = document.createElement("span");
    label.className = "form-label-inline";
    label.textContent = humanizeKey(key);
    row.appendChild(label);
    row.appendChild(createFormValue(value));
    wrapper.appendChild(row);
  });
  return wrapper;
};

const renderForms = (forms) => {
  const container = document.createElement("div");
  container.className = "entry-forms";
  if (!forms || Object.keys(forms).length === 0) {
    const message = document.createElement("p");
    message.className = "indec";
    message.textContent = "Indeclinable";
    container.appendChild(message);
    return container;
  }

  if (isSimpleNounForms(forms)) {
    container.appendChild(renderSimpleNounTable(forms));
    return container;
  }

  if (isNounForms(forms)) {
    container.appendChild(renderNounTable(forms));
    return container;
  }

  if (isAdjectiveForms(forms)) {
    container.appendChild(renderAdjectiveTable(forms));
    return container;
  }

  if (isVerbForms(forms)) {
    container.appendChild(renderVerbTable(forms));
    return container;
  }

  container.appendChild(renderGenericFormGroup(forms));
  return container;
};

const createEntryRow = (entry) => {
  const row = document.createElement("article");
  row.className = "row";

  const wordColumn = document.createElement("div");
  wordColumn.className = "col";
  const title = document.createElement("p");
  title.className = "title";
  title.lang = "uk";
  title.appendChild(renderText(entry.word));
  wordColumn.appendChild(title);

  const meta = document.createElement("p");
  meta.className = "subtitle";
  const details = [`${entry.pos}`];
  if (entry.info) details.push(entry.info);
  meta.textContent = details.join(" — ");
  wordColumn.appendChild(meta);

  if (Array.isArray(entry.defs) && entry.defs.length) {
    const defsList = document.createElement("ul");
    defsList.className = "entry-list";
    entry.defs.forEach((def) => {
      const item = document.createElement("li");
      item.appendChild(renderText(def));
      defsList.appendChild(item);
    });
    wordColumn.appendChild(defsList);
  }

  const wiktionaryLink = buildWiktionaryLink(entry.word);
  const linkWrapper = document.createElement("p");
  linkWrapper.className = "entry-link";
  linkWrapper.appendChild(wiktionaryLink);
  wordColumn.appendChild(linkWrapper);

  const formsColumn = document.createElement("div");
  formsColumn.className = "col";
  formsColumn.appendChild(renderForms(entry.forms));

  row.appendChild(wordColumn);
  row.appendChild(formsColumn);
  return row;
};

const exactMatchScore = (entry, query) => {
  if (!query) return 0;
  if (entry.normalizedWord === query) return 4;
  if (
    entry.normalizedWord.startsWith(`${query} `) ||
    entry.normalizedWord.endsWith(` ${query}`) ||
    entry.normalizedWord.includes(` ${query} `)
  )
    return 3;
  if (
    entry.normalizedDefs.includes(query) ||
    entry.normalizedForms.includes(query)
  )
    return 2;
  if (entry.normalizedWord.includes(query)) return 1;
  return 0;
};

const compareEntries = (a, b) => {
  if (sortInfo === "alpha") {
    return a.normalizedWord.localeCompare(b.normalizedWord, "uk");
  }
  if (sortInfo === "alpha_rev") {
    return b.normalizedWord.localeCompare(a.normalizedWord, "uk");
  }
  return a.index - b.index;
};

const FILTER_LABELS = {
  adjective: "Adjectives",
  adverb: "Adverbs",
  noun: "Nouns",
  numeral: "Numerals",
  particle: "Particles",
  phrase: "Phrases",
  pronoun: "Pronouns",
  proverb: "Proverbs",
  symbol: "Symbols",
  verb: "Verbs",
};

const getFilterLabel = (filter) => FILTER_LABELS[filter] || filter;

const applyTheme = (theme) => {
  document.body.classList.remove("theme-light", "theme-dark");
  if (theme === "light") document.body.classList.add("theme-light");
  if (theme === "dark") document.body.classList.add("theme-dark");
};

const resolveTheme = () => {
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
};

const updateSummary = () => {
  if (!words.length) {
    resultCount.textContent = "Loading dictionary...";
    return;
  }

  if (!filteredWords.length) {
    resultCount.textContent = "No entries match your search.";
    return;
  }

  const shown = Math.min(filteredWords.length, currentPage * RESULTS_PER_PAGE);
  const total = filteredWords.length;
  const plural = total === 1 ? "entry" : "entries";
  const parts = [`Showing ${shown} of ${total} ${plural}`];
  if (curFilter) parts.push(`filtered by ${getFilterLabel(curFilter)}`);
  if (sortInfo && sortInfo !== "freq")
    parts.push(`sorted by ${sortInfo.replace("_", " ")}`);
  resultCount.textContent = `${parts.join(" · ")}.`;
};

const renderResults = () => {
  dictionaryList.innerHTML = "";

  if (!filteredWords.length) {
    const emptyState = document.createElement("div");
    emptyState.className = "row";

    const message = document.createElement("p");
    message.textContent = "No results were found for this search.";
    emptyState.appendChild(message);

    if (searchTerm) {
      const link = buildWiktionaryLink(
        searchTerm,
        "Search Wiktionary for this word.",
        "wiktionary-link",
      );
      const hint = document.createElement("p");
      hint.appendChild(link);
      emptyState.appendChild(hint);
    }

    dictionaryList.appendChild(emptyState);
    return;
  }

  const start = 0;
  const end = Math.min(filteredWords.length, currentPage * RESULTS_PER_PAGE);
  filteredWords.slice(start, end).forEach((entry) => {
    dictionaryList.appendChild(createEntryRow(entry));
  });

  const existingMore = document.getElementById("loadMore");
  if (existingMore) existingMore.remove();

  if (filteredWords.length > end) {
    const loadMore = document.createElement("button");
    loadMore.id = "loadMore";
    loadMore.type = "button";
    loadMore.className = "button button--primary";
    loadMore.textContent = "Show more";
    loadMore.addEventListener("click", () => {
      currentPage += 1;
      renderResults();
      updateSummary();
    });
    const wrapper = document.createElement("div");
    wrapper.className = "load-more";
    wrapper.appendChild(loadMore);
    dictionaryList.appendChild(wrapper);
  }
};

const setURL = () => {
  const params = new URLSearchParams();
  if (searchTerm) params.set("q", searchTerm);
  if (curFilter) params.set("f", curFilter);
  if (sortInfo && sortInfo !== "freq") params.set("s", sortInfo);
  const url = `${window.location.pathname}${params.size > 0 ? "?" + params.toString() : ""}`;
  window.history.pushState(null, "", url);
};
const debouncedSetURL = debounce(setURL, 500);

const readURL = () => {
  const params = new URLSearchParams(window.location.search);
  searchTerm = params.get("q") || "";
  curFilter = params.get("f") || "";
  sortInfo = params.get("s") || "freq";

  searchInput.value = searchTerm;
  filterSelect.value = curFilter;
  sortSelect.value = sortInfo;
};

const applyMessageQuery = (message) => {
  if (!message || typeof message !== "object") return false;
  const { q, f, s } = message;
  let changed = false;

  if (typeof q === "string" && q.trim() !== searchTerm) {
    searchInput.value = q.trim();
    changed = true;
  }
  if (typeof f === "string" && f !== curFilter) {
    filterSelect.value = f;
    changed = true;
  }
  if (typeof s === "string" && s !== sortInfo) {
    sortSelect.value = s;
    changed = true;
  }

  return changed;
};

const searchHelper = () => {
  const query = normalizeText(searchTerm);
  filteredWords = words.filter((entry) => {
    if (curFilter && entry.pos !== curFilter) return false;
    if (!query) return true;
    return (
      entry.normalizedWord.includes(query) ||
      entry.normalizedDefs.includes(query) ||
      entry.normalizedForms.includes(query)
    );
  });

  filteredWords.sort((a, b) => {
    const scoreA = exactMatchScore(a, query);
    const scoreB = exactMatchScore(b, query);
    if (scoreB !== scoreA) return scoreB - scoreA;
    return compareEntries(a, b);
  });
};

const update = () => {
  searchHelper();
  renderResults();
  updateSummary();
  debouncedSetURL();
};

const clear = () => {
  searchTerm = "";
  curFilter = "";
  sortInfo = "freq";
  currentPage = 1;
  searchInput.value = "";
  filterSelect.value = "";
  sortSelect.value = "freq";
  searchInput.focus();
  update();
};

const search = () => {
  searchTerm = searchInput.value.trim();
  currentPage = 1;
  update();
};
const pasteFromClipboard = async () => {
  if (!navigator.clipboard) {
    searchInput.focus();
    return;
  }

  try {
    const text = await navigator.clipboard.readText();
    if (!text) return;
    searchInput.value = text.trim();
    search();
  } catch (error) {
    console.warn("Clipboard paste failed:", error);
    searchInput.focus();
  }
};

const select = () => {
  sortInfo = sortSelect.value;
  currentPage = 1;
  update();
};

const filter = () => {
  curFilter = filterSelect.value;
  currentPage = 1;
  update();
};

const showError = (message) => {
  dictionaryList.innerHTML = "";
  const errorRow = document.createElement("div");
  errorRow.className = "row";
  const errorText = document.createElement("p");
  errorText.textContent = `Unable to load dictionary data: ${message}`;
  errorText.style.color = "var(--stress)";
  errorRow.appendChild(errorText);
  dictionaryList.appendChild(errorRow);
  resultCount.textContent = "Failed to load data.";
};

const loadWords = async () => {
  resultCount.textContent = "Loading dictionary...";
  try {
    const response = await fetch("words.json");
    if (!response.ok) throw new Error(response.statusText || "Fetch failed");
    const data = await response.json();
    words = data.map(buildIndex);
    filteredWords = [...words];
    update();
  } catch (error) {
    showError(error.message || error.toString());
  }
};

const bindEvents = () => {
  clearButton.addEventListener("click", clear);
  searchInput.addEventListener("input", () => {
    search();
  });
  searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      clear();
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
    }
  });
  sortSelect.addEventListener("change", select);
  filterSelect.addEventListener("change", filter);
  pasteButton.addEventListener("click", pasteFromClipboard);
  const toolbar = document.getElementById("toolbar");
  toolbar.addEventListener("submit", (event) => {
    event.preventDefault();
  });
  window.addEventListener("keydown", (event) => {
    if (event.key === "F3" || (event.ctrlKey && event.key === "f")) {
      event.preventDefault();
      searchInput.focus();
    }
  });

  window.addEventListener("message", (event) => {
    if (event.source !== window.opener) return;
    if (!event.data || typeof event.data !== "object") return;

    const changed = applyMessageQuery(event.data);
    if (changed) {
      search();
    }
  });

  window.addEventListener("popstate", () => {
    readURL();
    update();
  });
};

const init = () => {
  applyTheme(resolveTheme());
  readURL();
  bindEvents();
  loadWords();
};

window.addEventListener("DOMContentLoaded", init);
