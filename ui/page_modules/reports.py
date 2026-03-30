"""
Reports page — per-topic results, CSV/Excel export, audit log viewer.
"""
import streamlit as st

from ui.utils import api_client as api
from ui.utils.components import (
    navigate,
    page_header,
    render_vote_results,
    show_error,
    show_info,
)


def render():
    page_header("Reports & Results", "Voting statistics and exports")

    token = st.session_state.get("token")
    user = st.session_state.get("user", {})
    is_admin = user.get("is_admin", False)

    tab_labels = ["📋 Summary", "📊 Detailed Report"]
    if is_admin:
        tab_labels.append("🔍 Audit Log")

    tabs = st.tabs(tab_labels)

    with tabs[0]:
        _render_summary(token)

    with tabs[1]:
        _render_detail(token, is_admin)

    if is_admin:
        with tabs[2]:
            _render_audit(token)


def _render_summary(token: str):
    st.markdown("### All Topics Summary")
    with st.spinner("Loading …"):
        summaries = api.get_all_topics_summary(token)

    if not summaries:
        show_info("No topics found.")
        return

    import pandas as pd

    df = pd.DataFrame(summaries)
    df.rename(
        columns={
            "topic_id": "ID",
            "title": "Title",
            "mode": "Mode",
            "status": "Status",
            "total_votes": "Votes Cast",
            "total_eligible": "Eligible",
            "participation_pct": "Participation %",
        },
        inplace=True,
    )
    st.dataframe(df.set_index("ID"), use_container_width=True)


def _render_detail(token: str, is_admin: bool):
    st.markdown("### Per-Topic Detailed Report")

    with st.spinner("Loading topics …"):
        summaries = api.get_all_topics_summary(token)

    if not summaries:
        show_info("No topics found.")
        return

    topic_options = {f"{t['title']} ({t['status']})": t["topic_id"] for t in summaries}
    selected_label = st.selectbox("Select Topic", list(topic_options.keys()))
    topic_id = topic_options[selected_label]

    with st.spinner("Loading results …"):
        results = api.get_vote_results(topic_id, token)

    if not results.get("success"):
        show_error(results.get("message", "Failed to load results."))
        return

    render_vote_results(results)

    if is_admin:
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 Export CSV", use_container_width=True):
                data = api.export_csv(topic_id, token)
                if data:
                    st.download_button(
                        "Download CSV",
                        data=data,
                        file_name=f"topic_{topic_id}_results.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
                else:
                    show_error("Export failed.")
        with col2:
            if st.button("📊 Export Excel", use_container_width=True):
                data = api.export_excel(topic_id, token)
                if data:
                    st.download_button(
                        "Download Excel",
                        data=data,
                        file_name=f"topic_{topic_id}_results.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
                else:
                    show_error("Export failed.")


def _render_audit(token: str):
    st.markdown("### Audit Log")

    col1, col2 = st.columns([3, 1])
    with col1:
        action_filter = st.text_input("Filter by action keyword", placeholder="VOTE_CAST")
    with col2:
        limit = st.number_input("Max rows", min_value=10, max_value=500, value=100)

    with st.spinner("Loading …"):
        logs = api.get_audit_logs(token, limit=limit, action_filter=action_filter or None)

    if not logs:
        show_info("No audit logs found.")
        return

    import pandas as pd

    df = pd.DataFrame(logs)
    df = df[["id", "timestamp", "action", "user_id", "apartment_id", "ip_address", "metadata"]]
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    st.dataframe(df.set_index("id"), use_container_width=True)
