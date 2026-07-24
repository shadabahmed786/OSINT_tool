import requests
import streamlit as st

st.set_page_config(page_title="OSINT Investigation Platform", layout="wide")

API_BASE = "http://localhost:8000"

st.title("Local-First OSINT Investigation Platform")
page = st.sidebar.radio("Go to", ["New Investigation", "Investigation View", "Pending Pivots"])

if page == "New Investigation":
    selector = st.text_input("Target Selector (Email, Username, Phone)")
    selector_type = st.selectbox("Selector Type", ["email", "username", "phone", "domain"])
    if st.button("Start Investigation"):
        response = requests.post(f"{API_BASE}/investigations/new", params={"selector": selector, "selector_type": selector_type})
        if response.ok:
            inv_id = response.json()["investigation_id"]
            st.success(f"Started! Investigation ID: {inv_id}")
            st.session_state["active_inv_id"] = inv_id

elif page == "Investigation View":
    inv_id = st.text_input("Active Investigation ID", value=st.session_state.get("active_inv_id", ""))
    if inv_id and st.button("Execute Enumeration"):
        with st.spinner("Running free enumeration adapters..."):
            response = requests.post(f"{API_BASE}/investigations/{inv_id}/run")
            if response.ok:
                st.success(f"Scan complete. Hits found: {response.json()['hits_found']}")
    if inv_id:
        st.json(requests.get(f"{API_BASE}/investigations/{inv_id}/graph").json())

elif page == "Pending Pivots":
    st.info("Newly discovered selectors require explicit human approval before automated pivoting.")
