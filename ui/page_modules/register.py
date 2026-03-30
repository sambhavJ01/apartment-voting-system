"""
Registration page — two steps:
  Step 1: Enter name, apartment number, phone number → send OTP
  Step 2: Enter 6-digit OTP to verify phone → account goes to pending approval
"""
import streamlit as st

from ui.utils import api_client as api
from ui.utils.components import navigate, page_header, show_error, show_info, show_success, show_warning


def render():
    page_header("Register", "Create your voter account")

    step = st.session_state.get("reg_step", "form")

    if step == "form":
        _render_form()
    elif step == "otp":
        _render_otp()


# ─── Step 1: registration form ───────────────────────────────────────────────

def _render_form():
    st.markdown("Fill in your details. You'll receive a WhatsApp OTP to verify your phone.")
    st.markdown("---")

    with st.form("register_form"):
        name = st.text_input("Full Name *", placeholder="e.g. Priya Sharma")
        apt = st.text_input("Apartment Number *", placeholder="e.g. 402, B-12, Tower-3/501")
        phone = st.text_input(
            "WhatsApp Phone Number *",
            placeholder="+919876543210",
            help="Include country code, e.g. +91xxxxxxxxxx",
        )
        submitted = st.form_submit_button("📱 Send OTP via WhatsApp", use_container_width=True)

    if submitted:
        if not all([name.strip(), apt.strip(), phone.strip()]):
            show_error("All fields are required.")
            return

        with st.spinner("Sending OTP …"):
            result = api.register(name.strip(), apt.strip(), phone.strip())

        if result.get("success"):
            st.session_state["reg_phone"] = phone.strip()
            st.session_state["reg_name"] = name.strip()
            st.session_state["reg_step"] = "otp"
            # Show debug OTP in development mode
            if result.get("debug_otp"):
                show_warning(f"[DEV] OTP is: **{result['debug_otp']}** (console mode only)")
            show_success("OTP sent! Check your WhatsApp.")
            st.rerun()
        else:
            show_error(result.get("message", "Registration failed."))

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Back to Home", use_container_width=True):
            navigate("home")
    with col2:
        if st.button("Already registered? Login →", use_container_width=True):
            navigate("login")


# ─── Step 2: OTP verification ────────────────────────────────────────────────

def _render_otp():
    phone = st.session_state.get("reg_phone", "")
    st.markdown(f"An OTP was sent to **{phone}** via WhatsApp.")
    st.markdown("---")

    with st.form("otp_form"):
        otp = st.text_input(
            "Enter 6-digit OTP *",
            max_chars=6,
            placeholder="123456",
        )
        submitted = st.form_submit_button("✅ Verify OTP", use_container_width=True)

    if submitted:
        if len(otp.strip()) != 6 or not otp.strip().isdigit():
            show_error("Please enter a valid 6-digit numeric OTP.")
            return

        with st.spinner("Verifying OTP …"):
            result = api.verify_registration_otp(phone, otp.strip())

        if result.get("success"):
            st.session_state["reg_step"] = "form"  # reset
            show_success(result.get("message", "Phone verified!"))
            st.balloons()
            show_info("An admin will review your registration shortly. You'll receive your password once approved.")
            st.markdown("---")
            if st.button("Go to Login", use_container_width=True):
                navigate("login")
        else:
            show_error(result.get("message", "OTP verification failed."))

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Re-enter Details", use_container_width=True):
            st.session_state["reg_step"] = "form"
            st.rerun()
    with col2:
        if st.button("🔄 Resend OTP", use_container_width=True):
            with st.spinner("Resending …"):
                result = api.resend_otp(phone, "registration")
            if result.get("success"):
                show_success("New OTP sent.")
                if result.get("debug_otp"):
                    show_warning(f"[DEV] OTP is: **{result['debug_otp']}**")
            else:
                show_error(result.get("message", "Could not resend OTP."))
