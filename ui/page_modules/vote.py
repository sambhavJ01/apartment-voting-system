"""
Voting page — browse active topics, select option, confirm via WhatsApp OTP.

Flow:
  1. List active topics with "has voted" badge
  2. User selects a topic → sees options
  3. User selects an option → OTP is sent
  4. User enters OTP → vote is recorded
  5. After voting: voter sees only their own choice.
     Full aggregate results are restricted to appointed election observers + admin.
"""
from datetime import datetime

import streamlit as st

from ui.utils import api_client as api
from ui.utils.components import (
    countdown_timer_js,
    navigate,
    page_header,
    render_vote_results,
    show_error,
    show_info,
    show_success,
    show_warning,
)


def render():
    page_header("Cast Your Vote", "Active voting topics")

    token = st.session_state.get("token")
    user = st.session_state.get("user", {})

    # Show which user is logged in
    st.markdown(
        f"Logged in as **{user.get('name')}** · "
        f"Apartment **{user.get('apartment_number')}**"
    )

    step = st.session_state.get("vote_step")

    if step == "otp_pending":
        _render_otp_confirmation(token)
    elif step == "voted":
        _render_voted_result(token)
    else:
        _render_topic_list(token)


# ─── Topic list ───────────────────────────────────────────────────────────────

def _render_topic_list(token: str):
    with st.spinner("Loading topics …"):
        topics = api.get_active_topics(token)

    if not topics:
        show_info("No active voting topics right now. Check back later.")
        return

    st.markdown("---")
    for topic in topics:
        _render_topic_card(topic, token)


def _render_topic_card(topic: dict, token: str):
    voted = topic.get("has_voted", False)
    mode_badge = "🔒 Anonymous" if topic["mode"] == "anonymous" else "👤 Identified"
    voted_badge = " · ✅ You have voted" if voted else ""

    with st.expander(f"**{topic['title']}** — {mode_badge}{voted_badge}", expanded=not voted):
        if topic.get("description"):
            st.markdown(topic["description"])

        if topic.get("end_time"):
            st.markdown(f"**Closes:** {topic['end_time'][:16].replace('T', ' ')} UTC")
            countdown_timer_js(topic["end_time"])

        if voted:
            st.info("You have already cast your vote for this topic.")
            # Always available: see your own choice
            if st.button(f"🪪 View My Vote", key=f"myv_{topic['id']}"):
                with st.spinner("Fetching your vote …"):
                    my_vote = api.get_my_vote(topic["id"], token)
                _render_my_vote_card(my_vote)
            # Full results only for observers / admin
            if topic.get("is_observer") or st.session_state.get("user", {}).get("is_admin"):
                if st.button(f"📊 View Results", key=f"res_{topic['id']}"):
                    with st.spinner("Loading results …"):
                        results = api.get_vote_results(topic["id"], token)
                    render_vote_results(results)
            return

        # Option selection
        options = topic.get("options", [])
        option_map = {o["text"]: o["id"] for o in options}
        selected_text = st.radio(
            "Choose your option:",
            list(option_map.keys()),
            key=f"opt_{topic['id']}",
        )

        if st.button(
            f"🗳️ Vote & Confirm via WhatsApp OTP",
            key=f"vote_{topic['id']}",
            use_container_width=True,
            type="primary",
        ):
            selected_id = option_map[selected_text]
            with st.spinner("Sending WhatsApp OTP …"):
                result = api.initiate_vote(topic["id"], selected_id, token)

            if result.get("success"):
                st.session_state["vote_step"] = "otp_pending"
                st.session_state["vote_topic_id"] = topic["id"]
                st.session_state["vote_option_id"] = selected_id
                st.session_state["vote_topic_title"] = topic["title"]
                st.session_state["vote_option_text"] = selected_text
                st.session_state["vote_is_observer"] = topic.get("is_observer", False)
                if result.get("debug_otp"):
                    show_warning(f"[DEV] OTP is: **{result['debug_otp']}**")
                st.rerun()
            else:
                show_error(result.get("message", "Failed to initiate vote."))


# ─── Post-vote: show only the voter's own choice ─────────────────────────────

def _render_my_vote_card(my_vote: dict):
    """Render a compact card showing just the voter's own selection."""
    if not my_vote.get("success"):
        show_error(my_vote.get("message", "Could not retrieve your vote."))
        return
    mode_note = (
        "(anonymous ballot)" if my_vote.get("mode") == "anonymous"
        else "(identified ballot)"
    )
    st.markdown(
        f"""
        <div style="background:#e8f5e9; border-left:4px solid #388e3c;
                    border-radius:8px; padding:1rem 1.5rem; margin-top:0.5rem;">
          <p style="margin:0; font-size:0.85rem; color:#555;">Your vote {mode_note}</p>
          <p style="margin:0.3rem 0 0 0; font-size:1.1rem;">
            <strong>{my_vote['topic_title']}</strong>
          </p>
          <p style="margin:0.3rem 0 0 0; font-size:1rem; color:#1b5e20;">
            ✔ {my_vote['option_text']}
          </p>
          <p style="margin:0.3rem 0 0 0; font-size:0.8rem; color:#888;">
            Cast at {my_vote['voted_at'][:16].replace('T', ' ')} UTC
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─── OTP confirmation ─────────────────────────────────────────────────────────

def _render_otp_confirmation(token: str):
    topic_title = st.session_state.get("vote_topic_title", "")
    option_text = st.session_state.get("vote_option_text", "")

    page_header("Confirm Your Vote", "Enter WhatsApp OTP to finalise")

    st.markdown(
        f"""
        <div style="background:#e3f2fd; border-radius:10px; padding:1rem 1.5rem; margin-bottom:1rem;">
          <p style="margin:0;"><strong>Topic:</strong> {topic_title}</p>
          <p style="margin:0;"><strong>Your choice:</strong> {option_text}</p>
          <p style="margin:0.5rem 0 0 0; color:#555; font-size:0.9rem;">
            An OTP has been sent to your registered WhatsApp number.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("vote_otp_form"):
        otp = st.text_input(
            "Enter 6-digit OTP *",
            max_chars=6,
            placeholder="123456",
        )
        col1, col2 = st.columns(2)
        with col1:
            confirmed = st.form_submit_button("✅ Confirm Vote", use_container_width=True, type="primary")
        with col2:
            cancel = st.form_submit_button("✖ Cancel", use_container_width=True)

    if cancel:
        st.session_state["vote_step"] = None
        st.rerun()

    if confirmed:
        if len(otp.strip()) != 6 or not otp.strip().isdigit():
            show_error("Please enter a valid 6-digit numeric OTP.")
            return

        topic_id = st.session_state["vote_topic_id"]
        option_id = st.session_state["vote_option_id"]

        with st.spinner("Casting your vote …"):
            result = api.cast_vote(topic_id, option_id, otp.strip(), token)

        if result.get("success"):
            st.session_state["vote_step"] = "voted"
            st.session_state["vote_result_topic_id"] = topic_id
            show_success(result.get("message", "Vote recorded!"))
            st.balloons()
            st.rerun()
        else:
            show_error(result.get("message", "Vote failed."))

    # Resend option
    st.markdown("---")
    if st.button("🔄 Resend OTP", use_container_width=True):
        user = st.session_state.get("user", {})
        phone = user.get("phone_number", "")
        with st.spinner("Resending …"):
            r = api.resend_otp(phone, "vote_confirmation")
        if r.get("success"):
            show_success("New OTP sent.")
            if r.get("debug_otp"):
                show_warning(f"[DEV] OTP is: **{r['debug_otp']}**")
        else:
            show_error(r.get("message", "Resend failed."))


# ─── Post-vote result display ─────────────────────────────────────────────────

def _render_voted_result(token: str):
    topic_id = st.session_state.get("vote_result_topic_id")

    page_header("✅ Vote Recorded!", "Thank you for participating")

    # Always show the voter's own choice — no timer, permanently visible
    if topic_id:
        with st.spinner("Fetching your vote …"):
            my_vote = api.get_my_vote(topic_id, token)
        _render_my_vote_card(my_vote)

    st.markdown("---")

    # Only observers (and admin) may view aggregate results
    is_obs = st.session_state.get("vote_is_observer", False)
    is_admin = st.session_state.get("user", {}).get("is_admin", False)
    if (is_obs or is_admin) and topic_id:
        if st.button("📊 View Full Results", use_container_width=True):
            with st.spinner("Loading results …"):
                results = api.get_vote_results(topic_id, token)
            render_vote_results(results)
    else:
        st.info(
            "Full results are available only to appointed election observers "
            "after the voting window closes."
        )

    st.markdown("")
    if st.button("← Back to Topics", use_container_width=True):
        st.session_state["vote_step"] = None
        navigate("vote")
