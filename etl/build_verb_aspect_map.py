#!/usr/bin/env python3
import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

CANDIDATE_RE = re.compile(r"(?:[А-Яа-яЁёЇїІіЄєҐґ](?:[\u0300-\u036f]*))+", re.UNICODE)
DIACRITIC_RE = re.compile(r"[\u0300-\u036f]")


def normalize_word(word: str) -> str:
    if word is None:
        return ""
    text = str(word).strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = DIACRITIC_RE.sub("", text)
    text = text.replace("ї", "і").replace("ґ", "г")
    text = text.replace("`", "").replace("'", "").replace('"', "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_candidates(raw_value: Optional[str]) -> List[str]:
    if not raw_value:
        return []
    value = str(raw_value)
    value = re.sub(r"<[^>]+>", "", value)
    value = value.replace(" or ", ",")
    candidates: List[str] = []
    for chunk in re.split(r"[,/;|]+", value):
        for match in CANDIDATE_RE.findall(chunk):
            candidate = normalize_word(match)
            if candidate:
                candidates.append(candidate)
    return candidates


def add_mapping(mapping: Dict[int, List[int]], src_indices: Sequence[int], target_indices: Sequence[int]) -> None:
    for src_idx in src_indices:
        mapping.setdefault(src_idx, [])
        for tgt_idx in target_indices:
            if tgt_idx != src_idx and tgt_idx not in mapping[src_idx]:
                mapping[src_idx].append(tgt_idx)
    for tgt_idx in target_indices:
        mapping.setdefault(tgt_idx, [])
        for src_idx in src_indices:
            if src_idx != tgt_idx and src_idx not in mapping[tgt_idx]:
                mapping[tgt_idx].append(src_idx)


def build_lookup(words: Sequence[dict]) -> Tuple[Dict[str, List[int]], Dict[str, List[int]], Set[int], Dict[int, Optional[int]]]:
    exact: Dict[str, List[int]] = {}
    normalized: Dict[str, List[int]] = {}
    verb_indices: Set[int] = set()
    frequency_by_index: Dict[int, Optional[int]] = {}
    for entry in words:
        idx = entry.get("index")
        if idx is None:
            continue
        if entry.get("pos") != "verb":
            continue
        verb_indices.add(idx)
        word = entry.get("word", "")
        exact_key = word.casefold()
        exact.setdefault(exact_key, []).append(idx)
        normalized_key = normalize_word(word)
        normalized.setdefault(normalized_key, []).append(idx)
        frequency = entry.get("freq")
        frequency_by_index[idx] = frequency if isinstance(frequency, int) else None
    return exact, normalized, verb_indices, frequency_by_index


def resolve_indices(word: str, exact: Dict[str, List[int]], normalized: Dict[str, List[int]], allowed_indices: Set[int]) -> List[int]:
    if word is None:
        return []
    key = str(word).casefold().strip()
    if key in exact:
        return [idx for idx in exact[key] if idx in allowed_indices]
    norm = normalize_word(word)
    return [idx for idx in normalized.get(norm, []) if idx in allowed_indices]


def parse_known_pairs_file(path: Path) -> List[Tuple[str, str]]:
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError(
            "Known pairs file must be a JSON array of [source, target] pairs."
        )

    pairs: List[Tuple[str, str]] = []
    for item in data:
        if not isinstance(item, list) or len(item) != 2:
            raise ValueError(
                "Each known pair must be a two-element array: [source, target]."
            )
        pairs.append((str(item[0]), str(item[1])))
    return pairs


def load_known_pairs(path: Path, exact: Dict[str, List[int]], normalized: Dict[str, List[int]], allowed_indices: Set[int], mapping: Dict[int, List[int]]) -> Tuple[int, Set[str], Set[str]]:
    if path is None:
        return 0, set(), set()

    pairs = parse_known_pairs_file(path)
    matched_sources: Set[str] = set()
    unmatched_sources: Set[str] = set()
    unmatched_targets: Set[str] = set()
    known_count = 0

    for source_word, target_word in pairs:
        source_indices = resolve_indices(source_word, exact, normalized, allowed_indices)
        if not source_indices:
            unmatched_sources.add(source_word)
            continue

        target_indices = resolve_indices(target_word, exact, normalized, allowed_indices)
        if not target_indices:
            unmatched_targets.add(target_word)
            continue

        add_mapping(mapping, source_indices, target_indices)
        matched_sources.add(source_word)
        known_count += 1

    return known_count, unmatched_sources, unmatched_targets


def sort_mapping_by_frequency(mapping: Dict[int, List[int]], frequency_by_index: Dict[int, Optional[int]]) -> None:
    def frequency_key(target_idx: int) -> float:
        frequency = frequency_by_index.get(target_idx)
        return frequency if frequency is not None else float("inf")

    for idx, targets in mapping.items():
        if len(targets) <= 1:
            continue
        mapping[idx] = sorted(targets, key=frequency_key)


def extract_companion_candidates(entry: dict) -> List[str]:
    candidates: List[str] = []
    for head_template in entry.get("head_templates", []):
        args = head_template.get("args", {})
        for key in ("impf", "pf"):
            if key in args:
                candidates.extend(extract_candidates(args[key]))
    if candidates:
        return candidates

    for form in entry.get("forms", []):
        tags = [str(t).lower() for t in form.get("tags", []) if t]
        if "infinitive" not in tags:
            continue
        if not any(t in ("perfective", "imperfective") for t in tags):
            continue
        for link in form.get("links", []):
            if isinstance(link, list) and len(link) >= 1 and isinstance(link[0], str):
                candidate = normalize_word(link[0])
                if candidate and candidate not in candidates:
                    candidates.append(candidate)
    return candidates


def main(words_path: Path, jsonl_path: Path, output_path: Path, limit: Optional[int] = None, known_pairs_path: Optional[Path] = None) -> None:
    words = json.loads(words_path.read_text(encoding="utf-8"))
    exact_lookup, normalized_lookup, verb_indices, frequency_by_index = build_lookup(words)
    mapping: Dict[int, List[int]] = {}

    known_pairs_count = 0
    known_unmapped_sources: Set[str] = set()
    known_unmapped_targets: Set[str] = set()
    if known_pairs_path is not None:
        known_pairs_count, known_unmapped_sources, known_unmapped_targets = load_known_pairs(
            known_pairs_path,
            exact_lookup,
            normalized_lookup,
            verb_indices,
            mapping,
        )

    total_lines = 0
    matched_sources: Set[str] = set()
    unmapped_sources: Set[str] = set()
    candidate_words: Set[str] = set()
    unmatched_candidates: Set[str] = set()

    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            if limit is not None and total_lines >= limit:
                break
            total_lines += 1
            if not line.strip():
                continue
            data = json.loads(line)
            if data.get("pos") != "verb":
                continue
            source_word = data.get("word")
            if not source_word:
                continue
            source_indices = resolve_indices(source_word, exact_lookup, normalized_lookup, verb_indices)
            if not source_indices:
                unmapped_sources.add(str(source_word))
                continue
            candidates = extract_companion_candidates(data)
            if not candidates:
                continue
            candidate_words.update(candidates)
            target_indices: List[int] = []
            for candidate in candidates:
                resolved = resolve_indices(candidate, exact_lookup, normalized_lookup, verb_indices)
                if resolved:
                    for idx in resolved:
                        if idx not in target_indices and idx not in source_indices:
                            target_indices.append(idx)
                else:
                    unmatched_candidates.add(candidate)
            if target_indices:
                add_mapping(mapping, source_indices, target_indices)
                matched_sources.add(str(source_word))

    mapped_count = len(mapping)
    total_verbs = sum(1 for entry in words if entry.get("pos") == "verb")
    sort_mapping_by_frequency(mapping, frequency_by_index)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = {
        str(idx): values[0] if len(values) == 1 else values
        for idx, values in sorted(mapping.items())
    }
    output_path.write_text(json.dumps(serialized, ensure_ascii=False, indent=2), encoding="utf-8")

    index_to_word = {
        entry["index"]: entry.get("word", "")
        for entry in words
        if entry.get("pos") == "verb" and entry.get("index") is not None
    }
    unmapped_indices = [idx for idx in sorted(verb_indices) if idx not in mapping]
    unmapped_words = [index_to_word[idx] for idx in unmapped_indices if index_to_word.get(idx)]

    print(f"Loaded {len(words)} word entries.")
    print(f"Found {total_verbs} verb entries in words.json.")
    print(f"Processed {total_lines} JSONL lines.")
    print(f"Mapped {mapped_count} entries to counterpart(s).")
    if known_pairs_path is not None:
        print(f"Loaded {known_pairs_count} known pair(s) from {known_pairs_path}.")
        print(f"Unresolved known source words: {len(known_unmapped_sources)}")
        print(f"Unresolved known target words: {len(known_unmapped_targets)}")
    print(f"Matched source verbs: {len(matched_sources)}")
    print(f"Unmapped source verbs (not in words.json): {len(unmapped_sources)}")
    print(f"Unmapped verb entries in words.json: {len(unmapped_words)}")
    if unmapped_words:
        sample = unmapped_words[:20]
        print("Sample unmapped words.json verbs:", sample)
    print(f"Unique companion candidates seen: {len(candidate_words)}")
    print(f"Unresolved companion candidates: {len(unmatched_candidates)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build verb aspect counterpart mapping from words.json and a Wiktionary verb JSONL dump."
    )
    parser.add_argument(
        "--words",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "words.json",
        help="Path to words.json",
    )
    parser.add_argument(
        "--jsonl",
        type=Path,
        # https://kaikki.org/dictionary/Ukrainian/pos-verb/index.html
        default=Path(__file__).resolve().parent / "data" / "kaikki.org-dictionary-Ukrainian-by-pos-verb.jsonl",
        help="Path to the verb JSONL file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "verb_aspect_mapping.json",
        help="Output mapping path",
    )
    parser.add_argument(
        "--known-pairs",
        type=Path,
        default=Path(__file__).resolve().parent / "verb_aspect_known_pairs.json",
        help="Optional path to a JSON file containing known verb aspect pairs as [[source, target], ...]",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on number of lines to process for testing",
    )
    args = parser.parse_args()
    main(args.words, args.jsonl, args.output, args.limit, args.known_pairs)
