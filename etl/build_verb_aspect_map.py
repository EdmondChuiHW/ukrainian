#!/usr/bin/env python3

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
    for form in entry.get("forms", []):
        tags = [str(t).lower() for t in form.get("tags", []) if t]
        if not any(t in ("perfective", "imperfective") for t in tags):
            continue
        for link in form.get("links", []):
            if isinstance(link, list) and len(link) >= 1 and isinstance(link[0], str):
                candidate = normalize_word(link[0])
                if candidate and candidate not in candidates:
                    candidates.append(candidate)
    if candidates:
        return candidates

    for head_template in entry.get("head_templates", []):
        args = head_template.get("args", {})
        for key in ("impf", "pf"):
            if key in args:
                candidates.extend(extract_candidates(args[key]))
    return candidates


def build_verb_counterpart_map(
    words_or_dictionary,
    jsonl_path: Path,
    limit: Optional[int] = None,
    known_pairs_path: Optional[Path] = None,
) -> Dict[int, List[int]]:
    words = (
        words_or_dictionary.get_final_forms()
        if hasattr(words_or_dictionary, 'get_final_forms')
        else words_or_dictionary
    )
    exact_lookup, normalized_lookup, verb_indices, frequency_by_index = build_lookup(words)
    mapping: Dict[int, List[int]] = {}

    if known_pairs_path is not None and known_pairs_path.exists():
        load_known_pairs(
            known_pairs_path,
            exact_lookup,
            normalized_lookup,
            verb_indices,
            mapping,
        )

    total_lines = 0
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

    sort_mapping_by_frequency(mapping, frequency_by_index)
    return mapping


def annotate_words_with_counterparts(words: Sequence[dict], mapping: Dict[int, List[int]]) -> None:
    for entry in words:
        idx = entry.get("index")
        if idx is None:
            continue
        counterparts = mapping.get(idx)
        if counterparts:
            entry["counterparts"] = counterparts


