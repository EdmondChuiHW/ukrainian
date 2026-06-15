#!/usr/bin/env python3
import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set, Tuple

DEFAULT_MAX_DETAILS = 50
ACCENT_MARK = "\u0301"


def load_json(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected a list at top level in {path}")
    return data


def normalize_word(word: str) -> str:
    return word.replace(ACCENT_MARK, "")


def extract_word_sets(entries: List[Dict[str, Any]]) -> Tuple[Set[str], Set[str], Dict[str, Set[str]]]:
    raw_words: Set[str] = set()
    normalized_to_raw: Dict[str, Set[str]] = {}
    for entry in entries:
        word = entry.get("word")
        if word is None:
            raise ValueError("Each entry must contain a 'word' field")
        raw_words.add(word)
        normalized = normalize_word(word)
        normalized_to_raw.setdefault(normalized, set()).add(word)
    normalized_words = set(normalized_to_raw)
    return raw_words, normalized_words, normalized_to_raw


def print_summary(label: str, raw_words: Iterable[str], normalized_words: Iterable[str]) -> None:
    print(f"{label}: {len(list(raw_words))} raw words, {len(list(normalized_words))} accentless words")


def format_words(words: Iterable[str]) -> str:
    return ", ".join(sorted(words))


def format_variants(normalized: str, variants: Set[str]) -> str:
    if len(variants) == 1:
        return next(iter(variants))
    return f"{normalized} [{', '.join(sorted(variants))}]"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare JSON word exports by raw words and accentless forms only.")
    parser.add_argument("old_file", type=Path, help="Path to the old JSON file")
    parser.add_argument("new_file", type=Path, help="Path to the new JSON file")
    parser.add_argument("--show-details", action="store_true", help="Show detailed differences")
    parser.add_argument("--max-details", type=int, default=DEFAULT_MAX_DETAILS, help="Maximum number of items to show")
    args = parser.parse_args()

    old_data = load_json(args.old_file)
    new_data = load_json(args.new_file)

    old_raw, old_normalized, old_variants = extract_word_sets(old_data)
    new_raw, new_normalized, new_variants = extract_word_sets(new_data)

    added_raw = sorted(new_raw - old_raw)
    removed_raw = sorted(old_raw - new_raw)
    added_normalized = sorted(new_normalized - old_normalized)
    removed_normalized = sorted(old_normalized - new_normalized)

    accent_only_changes = []
    for normalized in sorted(old_normalized & new_normalized):
        old_set = old_variants.get(normalized, set())
        new_set = new_variants.get(normalized, set())
        if old_set != new_set:
            accent_only_changes.append((normalized, old_set, new_set))

    print_summary("Old file", old_raw, old_normalized)
    print_summary("New file", new_raw, new_normalized)
    print(f"Added raw words: {len(added_raw)}")
    print(f"Removed raw words: {len(removed_raw)}")
    print(f"Added accentless words: {len(added_normalized)}")
    print(f"Removed accentless words: {len(removed_normalized)}")
    print(f"Accent-variant changes: {len(accent_only_changes)}")

    if args.show_details:
        detail_limit = args.max_details

        if added_raw:
            print("\nAdded raw words:")
            for word in added_raw[:detail_limit]:
                print(f"  {word}")
            if len(added_raw) > detail_limit:
                print(f"  ... and {len(added_raw) - detail_limit} more")

        if removed_raw:
            print("\nRemoved raw words:")
            for word in removed_raw[:detail_limit]:
                print(f"  {word}")
            if len(removed_raw) > detail_limit:
                print(f"  ... and {len(removed_raw) - detail_limit} more")

        if added_normalized:
            print("\nAdded accentless words:")
            for normalized in added_normalized[:detail_limit]:
                variants = new_variants.get(normalized, {normalized})
                print(f"  {format_variants(normalized, variants)}")
            if len(added_normalized) > detail_limit:
                print(f"  ... and {len(added_normalized) - detail_limit} more")

        if removed_normalized:
            print("\nRemoved accentless words:")
            for normalized in removed_normalized[:detail_limit]:
                variants = old_variants.get(normalized, {normalized})
                print(f"  {format_variants(normalized, variants)}")
            if len(removed_normalized) > detail_limit:
                print(f"  ... and {len(removed_normalized) - detail_limit} more")

        if accent_only_changes:
            print("\nAccent-only changes (same accentless word, variant forms differ):")
            for normalized, old_set, new_set in accent_only_changes[:detail_limit]:
                old_label = format_variants(normalized, old_set)
                new_label = format_variants(normalized, new_set)
                print(f"  {old_label} -> {new_label}")
            if len(accent_only_changes) > detail_limit:
                print(f"  ... and {len(accent_only_changes) - detail_limit} more")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
