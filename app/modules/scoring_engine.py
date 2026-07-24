from typing import List, Dict, Any

def score_and_rank_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Apply rule-based weighted confidence scoring to a list of raw platform findings.
    Returns findings updated with `confidence_score` and `confidence_tier`.
    """
    if not findings:
        return []

    total_hits = len(findings)

    # Calculate cross-platform corroboration boost
    corroboration_boost = min(total_hits * 5.0, 25.0)

    scored_findings = []

    for f in findings:
        base_score = 45.0
        rarity = f.get("rarity_weight", 1.0)

        # Signal 1: Display Name quality
        display_name = f.get("display_name")
        if display_name and str(display_name).strip():
            base_score += 10.0

        # Signal 2: Avatar URL present
        avatar_url = f.get("avatar_url")
        if avatar_url and str(avatar_url).strip():
            base_score += 10.0

        # Signal 3: Bio / Metadata detail richness
        bio = f.get("bio")
        if bio and len(str(bio).strip()) > 10:
            base_score += 10.0

        # Apply rarity weight and corroboration boost
        weighted_score = (base_score * rarity) + corroboration_boost

        # Cap between 0.0 and 100.0
        final_score = round(min(max(weighted_score, 10.0), 99.5), 1)

        # Determine Tier
        if final_score >= 75.0:
            tier = "HIGH"
        elif final_score >= 50.0:
            tier = "MEDIUM"
        else:
            tier = "LOW"

        updated_f = dict(f)
        updated_f["confidence_score"] = final_score
        updated_f["confidence_tier"] = tier
        scored_findings.append(updated_f)

    # Sort descending by score
    scored_findings.sort(key=lambda x: x["confidence_score"], reverse=True)
    return scored_findings
