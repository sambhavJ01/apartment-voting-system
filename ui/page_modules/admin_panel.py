"""
Admin panel — dashboard, user management, apartment management, topic management.
"""
import streamlit as st

from ui.utils import api_client as api
from ui.utils.components import (
    navigate,
    page_header,
    show_error,
    show_info,
    show_success,
    show_warning,
    stat_card,
)


def _load_approved_users(token: str) -> list:
    """Return (id, label) pairs for all approved non-admin users."""
    users = api.admin_all_users(token, "approved")
    return [
        {"id": u["id"], "label": f"{u['name']} • Apt {u['apartment_number']}"}
        for u in users
        if isinstance(u, dict)
    ]


def render():
    page_header("Admin Panel", "Manage voters, apartments and voting topics")

    token = st.session_state.get("token")

    tab_dash, tab_users, tab_apts, tab_topics = st.tabs(
        ["📊 Dashboard", "👥 Users", "🏢 Apartments", "🗳️ Topics"]
    )

    with tab_dash:
        _render_dashboard(token)

    with tab_users:
        _render_users(token)

    with tab_apts:
        _render_apartments(token)

    with tab_topics:
        _render_topics(token)


# ─── Dashboard ────────────────────────────────────────────────────────────────

def _render_dashboard(token: str):
    with st.spinner("Loading stats …"):
        stats = api.admin_dashboard(token)

    if "message" in stats and not stats.get("total_eligible_voters"):
        show_error(stats.get("message", "Failed to load dashboard."))
        return

    st.markdown("### Overview")
    c1, c2, c3 = st.columns(3)
    with c1:
        stat_card("Eligible Voters", stats.get("total_eligible_voters", 0))
    with c2:
        stat_card("Pending Approval", stats.get("total_pending_approval", 0))
    with c3:
        stat_card("Active Topics", stats.get("active_topics", 0))

    c4, c5, c6 = st.columns(3)
    with c4:
        stat_card("Total Votes Cast", stats.get("total_votes_cast", 0))
    with c5:
        stat_card("Total Apartments", stats.get("total_apartments", 0))
    with c6:
        stat_card("Participation %", f"{stats.get('overall_participation_pct', 0)}%")


# ─── User management ──────────────────────────────────────────────────────────

def _render_users(token: str):
    tabs = st.tabs(["⏳ Pending Approval", "📋 All Users"])

    with tabs[0]:
        _render_pending_users(token)

    with tabs[1]:
        _render_all_users(token)


def _render_pending_users(token: str):
    st.markdown("### Users Awaiting Approval")

    with st.spinner("Loading …"):
        users = api.admin_pending_users(token)

    if not users:
        show_info("No pending approvals. 🎉")
        return

    for user in users:
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
            with col1:
                st.markdown(f"**{user['name']}** — Apt {user['apartment_number']}")
                st.caption(f"📱 {user['phone_number']} · Registered {user['created_at'][:10]}")
            with col2:
                st.markdown(f"Status: `{user['status']}`")
            with col3:
                if st.button("✅ Approve", key=f"appr_{user['id']}", use_container_width=True, type="primary"):
                    with st.spinner("Approving …"):
                        result = api.admin_approve_user(user["id"], token)
                    if result.get("success"):
                        show_success(
                            f"Approved! **Password generated:** `{result.get('generated_password', 'N/A')}`  \n"
                            "_Share this password with the voter via a secure channel._"
                        )
                        st.rerun()
                    else:
                        show_error(result.get("message"))
            with col4:
                if st.button("❌ Reject", key=f"rej_{user['id']}", use_container_width=True):
                    with st.spinner("Rejecting …"):
                        result = api.admin_reject_user(user["id"], "Admin decision", token)
                    if result.get("success"):
                        show_warning("User rejected.")
                        st.rerun()
                    else:
                        show_error(result.get("message"))
        st.divider()


def _render_all_users(token: str):
    st.markdown("### All Voters")

    status_filter = st.selectbox(
        "Filter by status",
        ["All", "approved", "pending_approval", "rejected", "disabled", "pending_otp"],
        key="users_filter",
    )
    filter_val = None if status_filter == "All" else status_filter

    with st.spinner("Loading …"):
        users = api.admin_all_users(token, filter_val)

    if not users:
        show_info("No users found for the selected filter.")
        return

    for user in users:
        with st.container():
            col1, col2, col3 = st.columns([4, 2, 2])
            with col1:
                st.markdown(f"**{user['name']}** · Apt {user['apartment_number']}")
                st.caption(f"📱 {user['phone_number']} · {user['created_at'][:10]}")
            with col2:
                color = {"approved": "🟢", "rejected": "🔴", "disabled": "⚫"}.get(user["status"], "🟡")
                st.markdown(f"{color} `{user['status']}`")
                if user.get("approved_at"):
                    st.caption(f"Approved: {user['approved_at'][:10]}")
            with col3:
                if user["is_active"]:
                    if st.button("🔒 Disable", key=f"dis_{user['id']}", use_container_width=True):
                        result = api.admin_toggle_user(user["id"], False, token)
                        if result.get("success"):
                            show_warning("User disabled.")
                            st.rerun()
                        else:
                            show_error(result.get("message"))
                else:
                    if st.button("🔓 Enable", key=f"en_{user['id']}", use_container_width=True):
                        result = api.admin_toggle_user(user["id"], True, token)
                        if result.get("success"):
                            show_success("User enabled.")
                            st.rerun()
                        else:
                            show_error(result.get("message"))
        st.divider()


# ─── Apartment management ─────────────────────────────────────────────────────

def _render_apartments(token: str):
    st.markdown("### Manage Apartments")

    with st.expander("➕ Add New Apartment"):
        with st.form("add_apt_form"):
            apt_num = st.text_input("Apartment Number", placeholder="e.g. 501-A")
            max_voters = st.number_input("Max Allowed Voters", min_value=1, max_value=10, value=3)
            if st.form_submit_button("Create Apartment", use_container_width=True):
                result = api.admin_create_apartment(apt_num.strip(), max_voters, token)
                if result.get("success"):
                    show_success(result["message"])
                    st.rerun()
                else:
                    show_error(result.get("message"))

    st.markdown("---")
    with st.spinner("Loading apartments …"):
        apts = api.admin_list_apartments(token)

    if not apts:
        show_info("No apartments found. Add one above.")
        return

    for apt in apts:
        col1, col2, col3 = st.columns([3, 2, 2])
        with col1:
            status_icon = "🟢" if apt["is_active"] else "⚫"
            st.markdown(f"{status_icon} **Apt {apt['apartment_number']}**")
            st.caption(
                f"Max voters: {apt['max_allowed_voters']} · "
                f"Registered: {apt['registered_voters']}"
            )
        with col2:
            new_max = st.number_input(
                "Max voters", min_value=1, max_value=10,
                value=apt["max_allowed_voters"],
                key=f"maxv_{apt['id']}",
                label_visibility="collapsed",
            )
        with col3:
            if st.button("Update", key=f"upd_apt_{apt['id']}", use_container_width=True):
                result = api.admin_update_apartment(apt["id"], new_max, apt["is_active"], token)
                if result.get("success"):
                    show_success("Updated.")
                    st.rerun()
                else:
                    show_error(result.get("message"))
        st.divider()


# ─── Topic management ─────────────────────────────────────────────────────────

def _render_topics(token: str):
    st.markdown("### Manage Voting Topics")

    with st.expander("➕ Create New Topic"):
        _create_topic_form(token)

    st.markdown("---")
    st.markdown("#### Existing Topics")

    with st.spinner("Loading topics …"):
        topics = api.admin_list_topics(token)

    if not topics:
        show_info("No topics yet. Create one above.")
        return

    for topic in topics:
        _render_topic_admin_card(topic, token)


def _create_topic_form(token: str):
    approved_users = _load_approved_users(token)
    user_label_map = {u["label"]: u["id"] for u in approved_users}

    with st.form("create_topic_form"):
        title = st.text_input("Title *", placeholder="Election for Society President")
        description = st.text_area("Description", placeholder="Brief description of the voting topic")
        mode = st.selectbox("Voting Mode", ["anonymous", "identified"])

        col1, col2 = st.columns(2)
        with col1:
            start_time = st.date_input("Start Date (optional)", value=None)
            start_hour = st.time_input("Start Time", value=None, key="st_h")
        with col2:
            end_time = st.date_input("End Date (optional)", value=None)
            end_hour = st.time_input("End Time", value=None, key="et_h")

        st.markdown("**Options** (min 2, max 10 — one per line)")
        options_text = st.text_area(
            "Options",
            placeholder="Candidate A\nCandidate B\nCandidate C",
            height=120,
            label_visibility="collapsed",
        )

        st.markdown("**Election Observers** *(optional)*")
        st.caption(
            "Observers can view the full aggregated results. "
            "All other voters see only their own vote."
        )
        observer_labels = st.multiselect(
            "Select observers from approved residents",
            options=list(user_label_map.keys()),
            key="new_topic_observers",
            label_visibility="collapsed",
        )

        if st.form_submit_button("📋 Create Topic", use_container_width=True, type="primary"):
            options = [o.strip() for o in options_text.strip().splitlines() if o.strip()]
            if not title.strip():
                show_error("Title is required.")
                return
            if len(options) < 2:
                show_error("At least 2 options are required.")
                return

            start_dt = None
            end_dt = None
            try:
                if start_time and start_hour:
                    from datetime import datetime
                    start_dt = datetime.combine(start_time, start_hour)
                if end_time and end_hour:
                    from datetime import datetime
                    end_dt = datetime.combine(end_time, end_hour)
            except Exception:
                pass

            observer_ids = [user_label_map[lbl] for lbl in observer_labels]

            with st.spinner("Creating …"):
                result = api.admin_create_topic(
                    title.strip(), description.strip(), mode, options,
                    start_dt, end_dt, observer_ids=observer_ids, token=token
                )
            if result.get("success"):
                show_success(result["message"])
                st.rerun()
            else:
                show_error(result.get("message"))


def _render_topic_admin_card(topic: dict, token: str):
    status_colors = {
        "draft": "🔵", "active": "🟢", "closed": "⚫", "disabled": "🔴"
    }
    icon = status_colors.get(topic["status"], "⚪")

    with st.container():
        col1, col2 = st.columns([5, 3])
        with col1:
            st.markdown(
                f"{icon} **{topic['title']}** · "
                f"`{topic['mode']}` · `{topic['status']}`"
            )
            dates = ""
            if topic.get("start_time"):
                dates += f"Start: {topic['start_time'][:16].replace('T', ' ')}  "
            if topic.get("end_time"):
                dates += f"End: {topic['end_time'][:16].replace('T', ' ')}"
            if dates:
                st.caption(dates)
            # Show current observers
            observers = topic.get("observers", [])
            if observers:
                obs_names = ", ".join(o["name"] for o in observers)
                st.caption(f"👁️ Observers: {obs_names}")
            else:
                st.caption("🔒 No observers assigned — results not visible to voters")
        with col2:
            status_options = ["draft", "active", "closed", "disabled"]
            current_idx = status_options.index(topic["status"]) if topic["status"] in status_options else 0
            new_status = st.selectbox(
                "Status",
                status_options,
                index=current_idx,
                key=f"ts_{topic['id']}",
                label_visibility="collapsed",
            )
            if st.button("Update Status", key=f"upd_t_{topic['id']}", use_container_width=True):
                result = api.admin_update_topic_status(topic["id"], new_status, token)
                if result.get("success"):
                    show_success("Topic status updated.")
                    st.rerun()
                else:
                    show_error(result.get("message"))

        # Observer management
        with st.expander("👥 Manage Election Observers", expanded=False):
            approved_users = _load_approved_users(token)
            user_label_map = {u["label"]: u["id"] for u in approved_users}
            # Pre-select current observers
            current_obs_ids = {o["id"] for o in topic.get("observers", [])}
            current_labels = [
                lbl for lbl, uid in user_label_map.items() if uid in current_obs_ids
            ]
            selected_labels = st.multiselect(
                "Observers (can view full results)",
                options=list(user_label_map.keys()),
                default=current_labels,
                key=f"obs_{topic['id']}",
            )
            if st.button("💾 Save Observers", key=f"save_obs_{topic['id']}", use_container_width=True):
                new_ids = [user_label_map[lbl] for lbl in selected_labels]
                result = api.admin_set_observers(topic["id"], new_ids, token)
                if result.get("success"):
                    show_success(result["message"])
                    st.rerun()
                else:
                    show_error(result.get("message"))

        st.divider()
