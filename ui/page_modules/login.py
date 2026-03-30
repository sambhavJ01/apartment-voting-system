"""
Login page — supports both login methods:
  • Phone Number + Password
  • Apartment Number + Name + Password
"""
import streamlit as st

from ui.utils import api_client as api
from ui.utils.components import navigate, page_header, show_error, show_success


def render():
    page_header("Login", "Access your voting account")

    tab_phone, tab_apt = st.tabs(["📱 Login with Phone", "🏠 Login with Apartment"])

    with tab_phone:
        _phone_login()

    with tab_apt:
        _apartment_login()

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Back to Home", use_container_width=True):
            navigate("home")
    with col2:
        if st.button("New here? Register →", use_container_width=True):
            st.session_state["reg_step"] = "form"
            navigate("register")


def _phone_login():
    st.markdown("Enter your registered phone number and password.")
    with st.form("login_phone_form"):
        phone = st.text_input("Phone Number", placeholder="+919876543210")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", use_container_width=True)

    if submitted:
        if not phone.strip() or not password:
            show_error("Phone number and password are required.")
            return
        _do_login(password=password, phone_number=phone.strip())


def _apartment_login():
    st.markdown("Enter your apartment number, full name, and password.")
    with st.form("login_apt_form"):
        apt = st.text_input("Apartment Number", placeholder="402")
        name = st.text_input("Full Name", placeholder="Priya Sharma")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", use_container_width=True)

    if submitted:
        if not apt.strip() or not name.strip() or not password:
            show_error("All fields are required.")
            return
        _do_login(password=password, apartment_number=apt.strip(), name=name.strip())


def _do_login(**kwargs):
    with st.spinner("Logging in …"):
        result = api.login(**kwargs)

    if result.get("success"):
        st.session_state["token"] = result["access_token"]
        st.session_state["user"] = result["user"]
        show_success(f"Welcome, {result['user']['name']}! 👋")
        # Redirect admins to admin panel, everyone else to vote page
        if result["user"].get("is_admin"):
            navigate("admin")
        else:
            navigate("vote")
    else:
        show_error(result.get("message", "Login failed."))
