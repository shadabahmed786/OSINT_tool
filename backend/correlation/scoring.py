from backend.enumeration.base import Hit


def compute_rule_confidence(hit: Hit, total_hits_in_case: int, profile_picture_reused: bool) -> tuple[str, float]:
    score = 0.0

    obscure_platforms = ["Keybase", "Mastodon", "Matrix", "HackerNews"]
    score += 0.30 if hit.platform in obscure_platforms else 0.15

    if hit.bio and len(hit.bio) > 10:
        score += 0.20
    if hit.display_name:
        score += 0.15
    if profile_picture_reused:
        score += 0.25
    if total_hits_in_case >= 3:
        score += 0.10

    final_score = min(round(score, 2), 1.0)
    tier = "low"
    if final_score >= 0.70:
        tier = "high"
    elif final_score >= 0.40:
        tier = "medium"
    return tier, final_score
