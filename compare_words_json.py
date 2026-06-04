#!/usr/bin/env python3
import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

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


def make_group_key(entry: Dict[str, Any]) -> Tuple[str, str]:
    word = entry.get("word")
    pos = entry.get("pos")
    if word is None or pos is None:
        raise ValueError("Each entry must contain 'word' and 'pos' fields")
    return normalize_word(word), pos


def group_entries(entries: List[Dict[str, Any]]) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    result: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for entry in entries:
        key = make_group_key(entry)
        result.setdefault(key, []).append(entry)
    return result


def aggregate_group(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    agg: Dict[str, Any] = {}
    if not entries:
        return agg
    agg["word_variants"] = sorted({entry["word"] for entry in entries})
    agg["pos"] = entries[0]["pos"]
    all_keys = set().union(*(entry.keys() for entry in entries))
    all_keys.discard("word")
    all_keys.discard("pos")
    all_keys.discard("index")
    for key in sorted(all_keys):
        values = [normalize_value(entry.get(key)) for entry in entries]
        unique_values: List[Any] = []
        for value in values:
            if value not in unique_values:
                unique_values.append(value)
        agg[key] = unique_values[0] if len(unique_values) == 1 else unique_values
    return agg


def format_group_label(key: Tuple[str, str], groups: Dict[Tuple[str, str], List[Dict[str, Any]]]) -> str:
    normalized_word, pos = key
    variants = sorted({entry["word"] for entry in groups[key]})
    if len(variants) == 1:
        return f"{variants[0]} ({pos})"
    return f"{normalized_word} ({pos}) [{', '.join(variants)}]"


def group_keys_by_word(groups: Dict[Tuple[str, str], List[Dict[str, Any]]]) -> Dict[str, List[Tuple[str, str]]]:
    result: Dict[str, List[Tuple[str, str]]] = {}
    for key in groups:
        result.setdefault(key[0], []).append(key)
    return result


def normalize_def_string(value: str) -> str:
    suffixes = (
        " (determiner)",
        " (particle)",
        " (preposition)",
        " (pronoun)",
        " (noun)",
        " (adjective)",
        " (verb)",
        " (adverb)",
        " (proper noun)",
    )
    text = value.strip()
    for suffix in suffixes:
        if text.endswith(suffix):
            return text[: -len(suffix)].strip()
    return text


def normalize_field_for_pos_compare(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: normalize_field_for_pos_compare(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [normalize_field_for_pos_compare(item) for item in value]
    if isinstance(value, str):
        return normalize_def_string(value)
    return value


def normalize_grammar_for_pos_compare(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, dict) and all(v is None for v in value.values()):
        return None
    return normalize_field_for_pos_compare(value)


def normalize_aggregate_for_pos_compare(entry: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    keys = set(entry.keys()) - {"pos", "word_variants"}
    for key in sorted(keys):
        value = entry.get(key)
        if key == "grammar":
            result[key] = normalize_grammar_for_pos_compare(value)
        elif key == "defs":
            result[key] = normalize_field_for_pos_compare(value)
        else:
            result[key] = normalize_value(value)
    return result


def entries_equal_except_pos(old: Dict[str, Any], new: Dict[str, Any]) -> bool:
    keys = (set(old.keys()) | set(new.keys())) - {"pos", "word_variants"}
    for key in sorted(keys):
        old_val = normalize_aggregate_for_pos_compare(old).get(key)
        new_val = normalize_aggregate_for_pos_compare(new).get(key)
        if old_val != new_val:
            return False
    return True


def normalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: normalize_value(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [normalize_value(item) for item in value]
    return value


def compare_entries(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Tuple[Any, Any]]:
    changed = {}
    all_keys = set(old.keys()) | set(new.keys())
    all_keys.discard("index")
    for key in sorted(all_keys):
        old_val = normalize_value(old.get(key))
        new_val = normalize_value(new.get(key))
        if old_val != new_val:
            changed[key] = (old_val, new_val)
    return changed


def print_entry_summary(entries: Iterable[Dict[str, Any]], label: str) -> None:
    print(f"{label}: {len(list(entries))} entries")


def simple_diff_report(changed: Dict[str, Tuple[Any, Any]]) -> str:
    lines = []
    for field, (old_val, new_val) in changed.items():
        lines.append(f"  - {field}: old={json.dumps(old_val, ensure_ascii=False)} new={json.dumps(new_val, ensure_ascii=False)}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two word JSON exports and report differences.")
    parser.add_argument("old_file", type=Path, help="Path to the old JSON file")
    parser.add_argument("new_file", type=Path, help="Path to the new JSON file")
    parser.add_argument("--show-details", action="store_true", help="Show detailed field differences for modified entries")
    parser.add_argument("--max-details", type=int, default=DEFAULT_MAX_DETAILS, help="Maximum number of modified entries to show")
    args = parser.parse_args()

    old_data = load_json(args.old_file)
    new_data = load_json(args.new_file)

    old_groups = group_entries(old_data)
    new_groups = group_entries(new_data)

    old_keys = set(old_groups)
    new_keys = set(new_groups)
    added_keys = sorted(new_keys - old_keys)
    removed_keys = sorted(old_keys - new_keys)
    common_keys = sorted(old_keys & new_keys)

    old_word_keys = group_keys_by_word(old_groups)
    new_word_keys = group_keys_by_word(new_groups)
    pos_changes: List[Tuple[Tuple[str, str], Tuple[str, str]]] = []

    for word in sorted(set(old_word_keys) & set(new_word_keys)):
        old_candidates = [key for key in old_word_keys[word] if key not in common_keys]
        new_candidates = [key for key in new_word_keys[word] if key not in common_keys]
        if len(old_candidates) == 1 and len(new_candidates) == 1:
            old_key = old_candidates[0]
            new_key = new_candidates[0]
            old_agg = aggregate_group(old_groups[old_key])
            new_agg = aggregate_group(new_groups[new_key])
            if entries_equal_except_pos(old_agg, new_agg):
                pos_changes.append((old_key, new_key))

    for old_key, new_key in pos_changes:
        if old_key in removed_keys:
            removed_keys.remove(old_key)
        if new_key in added_keys:
            added_keys.remove(new_key)

    print_entry_summary(old_data, "Old file")
    print_entry_summary(new_data, "New file")
    print(f"Added entries: {len(added_keys)}")
    print(f"Removed entries: {len(removed_keys)}")
    print(f"Pos-only changes: {len(pos_changes)}")

    modified = []
    for key in common_keys:
        diff = compare_entries(aggregate_group(old_groups[key]), aggregate_group(new_groups[key]))
        if diff:
            modified.append((key, diff))

    print(f"Modified entries: {len(modified)}")

    detail_limit = args.max_details
    if added_keys:
        print("\nAdded entries (word, pos):")
        for key in random.sample(added_keys, min(detail_limit, len(added_keys))):
            print(f"  {format_group_label(key, new_groups)}")
        if len(added_keys) > detail_limit:
            print(f"  ... and {len(added_keys) - detail_limit} more")

    if removed_keys:
        print("\nRemoved entries (word, pos):")
        for key in random.sample(removed_keys, min(detail_limit, len(removed_keys))):
            print(f"  {format_group_label(key, old_groups)}")
        if len(removed_keys) > detail_limit:
            print(f"  ... and {len(removed_keys) - detail_limit} more")

    if pos_changes:
        print("\nPos-only changes:")
        for old_key, new_key in random.sample(pos_changes, min(detail_limit, len(pos_changes))):
            label = format_group_label(old_key, old_groups)
            print(f"  {label} -> {new_key[1]}")
        if len(pos_changes) > detail_limit:
            print(f"  ... and {len(pos_changes) - detail_limit} more")

    if args.show_details and modified:
        print("\nModified entries:")
        sampled = random.sample(modified, min(args.max_details, len(modified)))
        for key, diff in sampled:
            print(f"\n{format_group_label(key, new_groups)}:")
            print(simple_diff_report(diff))
        if len(modified) > args.max_details:
            print(f"\n... and {len(modified) - args.max_details} more modified entries")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
