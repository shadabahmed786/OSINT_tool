from difflib import SequenceMatcher


def similarity_score(left: str, right: str) -> float:
    return round(SequenceMatcher(None, left or "", right or "").ratio(), 4)
