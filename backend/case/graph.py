def generate_case_graph(db_connection, investigation_id: str) -> dict:
    cursor = db_connection.cursor()
    cursor.execute("SELECT id, selector_value, selector_type FROM selectors WHERE investigation_id = ?", (investigation_id,))
    selectors = cursor.fetchall()
    cursor.execute("SELECT id, matched_selector_id, platform, confidence_tier FROM hits WHERE investigation_id = ?", (investigation_id,))
    hits = cursor.fetchall()

    nodes = []
    edges = []

    for selector in selectors:
        nodes.append({"id": f"sel_{selector['id']}", "label": f"{selector['selector_type']}: {selector['selector_value']}", "type": "selector"})

    for hit in hits:
        hit_node_id = f"hit_{hit['id']}"
        nodes.append({"id": hit_node_id, "label": hit['platform'], "type": "hit", "tier": hit['confidence_tier']})
        edges.append({"source": f"sel_{hit['matched_selector_id']}", "target": hit_node_id})

    return {"nodes": nodes, "edges": edges}
