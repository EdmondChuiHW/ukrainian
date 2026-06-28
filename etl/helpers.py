import re
import unicodedata
from functools import lru_cache
from typing import Optional

try:
    STRESS_MARK = unicodedata.lookup('COMBINING ACUTE ACCENT')
except KeyError:
    STRESS_MARK = '́'

_MIXED_LATIN_TO_CYRILLIC = str.maketrans({
    'A': 'А', 'a': 'а',
    'B': 'В', 'E': 'Е', 'e': 'е',
    'K': 'К', 'k': 'к',
    'M': 'М', 'm': 'м',
    'O': 'О', 'o': 'о',
    'P': 'Р', 'p': 'р',
    'C': 'С', 'c': 'с',
    'T': 'Т', 't': 'т',
    'X': 'Х', 'x': 'х',
    'Y': 'У', 'y': 'у',
    'H': 'Н', 'h': 'н',
    'S': 'С', 's': 'с',
})


def _contains_cyrillic(text: str) -> bool:
    for ch in text:
        if '\u0400' <= ch <= '\u052f' or '\u2de0' <= ch <= '\u2dff' or '\ua640' <= ch <= '\ua69f':
            return True
    return False


def _contains_latin(text: str) -> bool:
    return any('A' <= ch <= 'Z' or 'a' <= ch <= 'z' for ch in text)


def _normalize_mixed_script(text: str) -> str:
    """Normalize text containing both Cyrillic and Latin characters.

    Some Kaikki entries mix Cyrillic letters with Latin-looking characters
    such as Latin 'á'. In those cases, we want to preserve the Cyrillic word
    shape when removing stress.

    Example:
        'Богдáна' -> 'Богдана'
    """
    if _contains_cyrillic(text) and _contains_latin(text):
        return text.translate(_MIXED_LATIN_TO_CYRILLIC)
    return text


@lru_cache(maxsize=None)
def strip_stress(text: Optional[str]) -> str:
    if text is None:
        return ''

    # Normalize to NFD first so precomposed accented characters become a base
    # letter plus combining accent. For example:
    #   'á' (U+00E1) -> 'a' + '́' (U+0301)
    #   'а́' (Cyrillic a with acute) -> 'а' + '́'
    # This allows a single remove operation to strip the stress mark
    # consistently across both decomposed and precomposed forms.
    normalized = unicodedata.normalize('NFD', str(text))
    stripped = normalized.replace(STRESS_MARK, '')

    # Fix mixed-script entries like 'Богдáна' before returning.
    fixed_mixed_script = _normalize_mixed_script(stripped)

    # then normalize back to NFC so decomposed letters like 'и' + breve
    # recombine into their composed forms (for example, 'й').
    return unicodedata.normalize('NFC', fixed_mixed_script)


@lru_cache(maxsize=None)
def strip_suffix_number(text: Optional[str]) -> str:
    """Strip trailing homograph number (e.g. 'мати 1' -> 'мати')."""
    if text is None:
        return ''
    parts = str(text).split()
    if parts and parts[-1].isdigit():
        return ' '.join(parts[:-1])
    return str(text)
