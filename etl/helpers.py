import unicodedata
from functools import lru_cache
from typing import Optional

try:
    STRESS_MARK = unicodedata.lookup('COMBINING ACUTE ACCENT')
except KeyError:
    STRESS_MARK = '́'

@lru_cache(maxsize=None)
def strip_stress(text: Optional[str]) -> str:
    if text is None:
        return ''
    normalized = unicodedata.normalize('NFD', str(text))
    return normalized.replace(STRESS_MARK, '')
