# Implementation Plan - Resolve Dictionary BUGS.md (Revised)

This revised plan incorporates your feedback to:

1. **Frontend-side Animacy Defaulting**: Keep `animacy` as `null` in the JSON output, but have the frontend default it to `'inanimate'` for all nouns when unspecified.
2. **Avoid String Parsing in Frontend**: Add structured `def_prefixes` to the JSON output and use those in the UI.
3. **Template inflection names**: Only match `adecl`, `ndecl`, and `conj` templates (avoiding non-existent ones).

---

## Proposed Changes

### ETL Pipeline (`etl` component)

#### [MODIFY] [extract.py](file:///Users/edmondc/ws/ukrainian/etl/extract.py)

1. **Structured Definition Prefixes (Fix `горіти` & `на`):**
   - Read definitions from the standard `glosses` list. Avoid `raw_glosses` or string replacements.
   - Construct a structured `prefix` string by combining the sense's `qualifier` and semantic `tags` (filtering out structural tags like `form-of` or `canonical`).
   - Package this prefix in the parsed definition JSON as a separate field (`prefix`):
     ```python
     prefix_parts = []
     if qualifier:
         q_str = qualifier.strip()
         if 'case' in q_str.lower() and not q_str.startswith('+'):
             q_str = f"+{q_str}"
         prefix_parts.append(q_str)
     for tag in tags or []:
         if tag not in ('form-of', 'alt-of', 'canonical', 'table-tags', 'inflection-template'):
             prefix_parts.append(tag)
     prefix = ", ".join(prefix_parts) if prefix_parts else None
     ```
   - Store the prefix in the definition dictionaries: `{'definition': g, 'prefix': prefix, ...}`.

2. **Template-Based Inflection Parsing (Fix `йому`, `наші`, pronoun inflections):**
   - Inspect the `inflection_templates` list to determine the `form_type` of the template:

     ```python
     inflection_templates = entry.get('inflection_templates') or []
     template_names = [t.get('name', '').lower() for t in inflection_templates if isinstance(t, dict)]

     form_type = None
     if any('conj' in name for name in template_names):
         form_type = 'verb'
     elif any('adecl' in name for name in template_names):
         form_type = 'adj'
     elif any('ndecl' in name for name in template_names):
         form_type = 'noun'
     ```

   - Fall back to standard POS mapping (`noun`, `verb`, `adjective`) if no explicit template matches.

3. **Normalize Determiners (Fix `той` duplicates):**
   - Map `'det': 'particle'` in `pos_map`.

4. **Clean Related/Derived Candidates (Fix `Україна` incorrect merges):**
   - Related/derived candidates get `definitions: []` and `info: None` so they don't copy and pollute other entries with the parent's definition.

5. **Animate Tag Mapping (Fix `окупант` animacy info):**
   - Map `'person': 'animate'` and `'animal': 'animate'` in `_ANIMACY_TAGS` to treat `person`/`animal` noun tags as animate.

---

#### [MODIFY] [dictionary.py](file:///Users/edmondc/ws/ukrainian/etl/dictionary.py)

1. **Structured Prefix Management:**
   - Add `self.def_prefixes = {}` to `Usage` to store prefixes mapped by definition string.
   - Update `Word.add_definition`, `Usage.add_definition`, and `Usage.merge` to accept and preserve `prefix`.
   - Update `Usage.get_dict` to output a `def_prefixes` array alongside the `defs` array in the final dictionary:
     ```python
     defs = self.get_definitions()
     prefixes = [self.def_prefixes.get(d) for d in defs]
     # ...
     if any(p is not None for p in prefixes):
         res['def_prefixes'] = prefixes
     ```

2. **Defective Words Preservation (Fix `є` missing definitions):**
   - If a candidate is a perfect match (`self.word == found_word`) but has no forms table (`form_type is None`), preserve it (`self.delete_me = False`).

3. **Normalize Determiners (Fix `той` duplicates):**
   - Add `'det': 'particle'` to `Word.normalize_pos` replace map.

---

### Frontend Components (`src` component)

#### [MODIFY] [words.ts](file:///Users/edmondc/ws/ukrainian/src/types/words.ts)

1. **Structured Prefix Type Definition:**
   - Add `def_prefixes?: (string | null)[];` to `RawDictionaryEntry` interface.

---

#### [MODIFY] [EntryRow.tsx](file:///Users/edmondc/ws/ukrainian/src/components/EntryRow.tsx)

1. **Frontend-side Noun Animacy Defaulting (Fix `окупант`):**
   - In `formatGrammar`, if `entry.grammar.animacy` is not specified and `entry.pos === 'noun'`, default it to `'inanimate'`:
     ```typescript
     const formatGrammar = (entry: DictionaryEntry): string | null => {
       if (entry.grammar) {
         const parts: string[] = [];
         if (entry.grammar.gender) parts.push(entry.grammar.gender);

         const animacy =
           entry.grammar.animacy || (entry.pos === 'noun' ? 'inanimate' : null);
         if (animacy) parts.push(animacy);

         if (entry.grammar.aspect) parts.push(entry.grammar.aspect);
         return parts.length > 0 ? parts.join(', ') : null;
       }
       return entry.info || null;
     };
     ```

2. **Collapsing Nested List UI using `def_prefixes`:**
   - Update `EntryRow` to read `entry.def_prefixes` and group definitions cleanly using the pre-compiled JSON prefixes:

     ```typescript
     interface GroupedDef {
       qualifier?: string;
       items: string[];
     }

     const groupDefinitions = (
       defs: string[],
       prefixes?: (string | null)[],
     ): GroupedDef[] => {
       const groups: GroupedDef[] = [];
       let currentGroup: GroupedDef | null = null;

       for (let i = 0; i < defs.length; i++) {
         const def = defs[i];
         const prefix = prefixes?.[i];
         if (prefix) {
           const formattedPrefix = `(${prefix})`;
           if (currentGroup && currentGroup.qualifier === formattedPrefix) {
             currentGroup.items.push(def);
           } else {
             currentGroup = { qualifier: formattedPrefix, items: [def] };
             groups.push(currentGroup);
           }
         } else {
           currentGroup = null;
           groups.push({ items: [def] });
         }
       }
       return groups;
     };
     ```

   - Render the grouped list natively with nested sub-lists using ordered `<ol>` components in the UI.

---

## Verification Plan

### Automated Tests

Run unit tests to ensure all existing tests pass:

```bash
.venv/bin/python -m unittest etl/test_etl.py
```

We will also add unit tests for:

- Related/derived candidates having empty definitions.
- Pronoun/numeral declension parsing using templates.

### Manual Verification

Validate compiled index/dictionary files and UI for:

- `Україна` (no extra definitions).
- `горіти` (definition has `(intransitive)` prefix).
- `на` (prepositions grouped under nested `(+accusative case)` and `(+locative case)` lists).
- `йому` and `наші` (resolved/collapsed).
- `є` (verb preserved).
- `той` (single entry).
- `окупант` (animacy marked as `animate`).
