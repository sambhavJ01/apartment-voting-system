"""
Main Streamlit application.

Navigation is state-driven via st.session_state["page"].
All pages are imported and rendered in a single file to share session state.
"""
import streamlit as st

from ui.utils.components import init_session, is_admin, is_logged_in, logout, navigate
from ui.page_modules import register, login, vote, admin_panel, reports


# ─── Inline page renderers (defined BEFORE being called below) ────────────────

def _render_home():
    st.markdown(
        """
        <div style="
            text-align: center;
            padding: 3rem 2rem 2rem 2rem;
        ">
            <span style="font-size: 5rem;">🗳️</span>
            <h1 style="font-size: 2.5rem; margin: 0.5rem 0;">Apartment Voting System</h1>
            <p style="font-size: 1.1rem; color: #555; max-width: 600px; margin: 0 auto 2rem auto;">
                Secure, transparent, and verifiable — vote on society matters with
                WhatsApp OTP confirmation. Supports both anonymous and identified voting modes.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### Get Started")

        if st.button("📝 Register as Voter", use_container_width=True, type="primary"):
            st.session_state["reg_step"] = "form"
            navigate("register")

        st.markdown(" ")

        if st.button("🔐 Login to Vote", use_container_width=True):
            navigate("login")

        st.markdown(" ")
        st.divider()
        st.markdown(
            """
            **How it works:**
            1. **Register** — Enter your details and verify your WhatsApp number
            2. **Admin Approval** — Your account is reviewed by the society admin
            3. **Vote** — Login, select your choice, confirm via WhatsApp OTP
            4. **Results** — View live participation statistics
            """
        )


def _render_bootstrap():
    """First-time admin account creation."""
    from ui.utils.components import page_header, show_error, show_success
    from ui.utils import api_client as api

    page_header("Admin Setup", "Create the first administrator account")

    st.warning(
        "⚠️ This is for first-time setup only. "
        "You need the ADMIN_REGISTRATION_KEY from your .env file."
    )

    with st.form("bootstrap_form"):
        name = st.text_input("Admin Name *")
        apt = st.text_input("Apartment Number *", placeholder="Admin/Office")
        phone = st.text_input("Phone Number *", placeholder="+919876543210")
        admin_key = st.text_input("Admin Registration Key *", type="password")
        submitted = st.form_submit_button("🚀 Create Admin Account", use_container_width=True, type="primary")

    if submitted:
        if not all([name.strip(), apt.strip(), phone.strip(), admin_key]):
            show_error("All fields are required.")
            return

        with st.spinner("Creating admin …"):
            result = api.bootstrap_admin(name.strip(), apt.strip(), phone.strip(), admin_key)

        if result.get("success"):
            show_success("Admin account created!")
            st.info(
                f"🔑 **Generated Password:** `{result.get('generated_password', 'N/A')}`  \n"
                "_Store this securely. Use it to log in as admin._"
            )
        else:
            show_error(result.get("message", "Failed to create admin."))

    if st.button("← Back to Home"):
        navigate("home")

# ─── Page config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Apartment Voting System",
    page_icon="🗳️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom global CSS ────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
    /* Wider input fields */
    .stTextInput input { font-size: 1rem !important; }
    /* Larger primary buttons */
    .stButton > button[kind="primary"] {
        font-size: 1.05rem !important;
        padding: 0.6rem 1rem !important;
    }
    /* Radio buttons — bigger tap targets */
    .stRadio > div { gap: 0.6rem !important; }
    .stRadio label { font-size: 1rem !important; }
    /* ── Sidebar base ─────────────────────────────────────────── */
    [data-testid="stSidebar"] { background: #1a237e !important; }
    [data-testid="stSidebar"] * { color: white !important; }
    /* Normal sidebar nav buttons */
    [data-testid="stSidebar"] .stButton > button {
        border: 1px solid rgba(255,255,255,0.35) !important;
        background: transparent !important;
        color: white !important;
        width: 100% !important;
        transition: background 0.15s ease !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(255,255,255,0.15) !important;
    }

    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Session initialisation ───────────────────────────────────────────────────

init_session()

# ─── Sidebar navigation ───────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(
        """
        <div style="text-align:center; padding:1rem 0 1.5rem 0;">
            <span style="font-size:2.5rem;">🗳️</span><br>
            <span style="font-size:1.1rem; font-weight:700;">Apartment Voting</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if is_logged_in():
        # ── Logged-in navigation ──────────────────────────────────
        user = st.session_state.get("user", {})
        st.markdown(
            f"**{user.get('name', 'User')}**  \n"
            f"Apt {user.get('apartment_number', '')}  \n"
            f"{'👑 Admin' if user.get('is_admin') else '👤 Voter'}"
        )
        st.divider()

        if st.button("🗳️ Vote", use_container_width=True):
            navigate("vote")

        if st.button("📊 Reports", use_container_width=True):
            navigate("reports")

        if is_admin():
            if st.button("⚙️ Admin Panel", use_container_width=True):
                navigate("admin")

        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            logout()

    else:
        # ── Guest navigation (not logged in) ─────────────────────
        if st.button("🏠 Home", use_container_width=True):
            navigate("home")

        if st.button("📝 Register", use_container_width=True):
            st.session_state["reg_step"] = "form"
            navigate("register")

        if st.button("🔐 Login", use_container_width=True):
            navigate("login")

    # ── Setup Admin — visually distinct, always at the bottom ────
    st.divider()
    if st.button("🔧 Setup Admin", use_container_width=True):
        navigate("bootstrap")

# ─── Main content area ────────────────────────────────────────────────────────

page = st.session_state.get("page", "home")

if page == "home":
    _render_home()

elif page == "register":
    register.render()

elif page == "login":
    login.render()

elif page == "vote":
    if not is_logged_in():
        st.warning("Please log in to vote.")
        login.render()
    else:
        vote.render()

elif page == "admin":
    if not is_logged_in() or not is_admin():
        st.error("Admin access only.")
    else:
        admin_panel.render()

elif page == "reports":
    if not is_logged_in():
        st.warning("Please log in to view reports.")
        login.render()
    else:
        reports.render()

elif page == "bootstrap":
    _render_bootstrap()

else:
    navigate("home")
