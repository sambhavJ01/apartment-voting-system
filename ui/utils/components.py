"""
Reusable Streamlit UI components and helpers.
"""
import streamlit as st


# ─── Session state helpers ────────────────────────────────────────────────────

def init_session():
    defaults = {
        "page": "home",
        "token": None,
        "user": None,
        "reg_phone": None,   # phone persisted between register ↔ otp steps
        "vote_step": None,   # None | "otp_pending"
        "vote_topic_id": None,
        "vote_option_id": None,
        "vote_topic_title": None,
        "vote_option_text": None,
        "vote_result": None,
        "show_result_until": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def navigate(page: str):
    st.session_state["page"] = page
    st.rerun()


def logout():
    for key in ["token", "user", "vote_step", "vote_topic_id", "vote_option_id",
                "vote_topic_title", "vote_option_text", "vote_result", "show_result_until"]:
        st.session_state[key] = None
    navigate("home")


def is_logged_in() -> bool:
    return bool(st.session_state.get("token"))


def is_admin() -> bool:
    user = st.session_state.get("user")
    return bool(user and user.get("is_admin"))


# ─── Notifications ────────────────────────────────────────────────────────────

def show_success(msg: str):
    st.success(f"✅ {msg}")


def show_error(msg: str):
    st.error(f"❌ {msg}")


def show_info(msg: str):
    st.info(f"ℹ️ {msg}")


def show_warning(msg: str):
    st.warning(f"⚠️ {msg}")


# ─── Page header ─────────────────────────────────────────────────────────────

def page_header(title: str, subtitle: str = ""):
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, #1a237e 0%, #283593 100%);
            padding: 1.5rem 2rem;
            border-radius: 12px;
            margin-bottom: 1.5rem;
        ">
            <h2 style="color:white; margin:0;">{title}</h2>
            {"<p style='color:#90caf9; margin:0.3rem 0 0 0;'>" + subtitle + "</p>" if subtitle else ""}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─── Stat card ────────────────────────────────────────────────────────────────

def stat_card(label: str, value, delta: str = None):
    st.metric(label=label, value=value, delta=delta)


# ─── Countdown timer (JS) ────────────────────────────────────────────────────

def countdown_timer_js(end_iso: str):
    """Inject a live countdown timer into the page."""
    st.markdown(
        f"""
        <div id="countdown" style="
            font-size:1.1rem; font-weight:600;
            color: #f44336; margin: 0.5rem 0;
        ">⏳ Loading timer…</div>
        <script>
        (function() {{
            var end = new Date("{end_iso}").getTime();
            function tick() {{
                var now = new Date().getTime();
                var diff = end - now;
                if (diff <= 0) {{
                    document.getElementById("countdown").innerHTML = "⏰ Voting has ended.";
                    return;
                }}
                var h = Math.floor(diff / 3600000);
                var m = Math.floor((diff % 3600000) / 60000);
                var s = Math.floor((diff % 60000) / 1000);
                document.getElementById("countdown").innerHTML =
                    "⏳ Time remaining: " + h + "h " + m + "m " + s + "s";
                setTimeout(tick, 1000);
            }}
            tick();
        }})();
        </script>
        """,
        unsafe_allow_html=True,
    )


# ─── Vote result display ──────────────────────────────────────────────────────

def render_vote_results(results: dict, show_details: bool = False):
    """Render a bar-chart style vote result."""
    if not results or not results.get("results"):
        st.info("No votes cast yet.")
        return

    st.markdown(f"**Total votes:** {results['total_votes']} &nbsp;|&nbsp; "
                f"**Participation:** {results['participation_pct']}%")

    for r in sorted(results["results"], key=lambda x: -x["vote_count"]):
        pct = r["percentage"]
        bar_width = max(int(pct), 1)
        st.markdown(
            f"""
            <div style="margin-bottom:0.75rem;">
              <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                <span style="font-weight:600;">{r['option_text']}</span>
                <span>{r['vote_count']} votes ({pct}%)</span>
              </div>
              <div style="background:#ddd; border-radius:4px; height:20px;">
                <div style="
                  background: linear-gradient(90deg, #1565C0, #42A5F5);
                  width:{bar_width}%; height:100%; border-radius:4px;
                "></div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
