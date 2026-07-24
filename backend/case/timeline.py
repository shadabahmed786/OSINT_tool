def build_timeline(evidence_log: list[dict]) -> list[dict]:
    return sorted(evidence_log, key=lambda row: row.get("timestamp", ""))
