"""Main Streamlit app entry point."""
import streamlit as st
from src.utils.auth import login_user, register_user
from src.utils.api_client import api_client

# Page config
st.set_page_config(
    page_title="Hospital Chatbot",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None

# Sidebar - Authentication
with st.sidebar:
    st.title("🏥 Hospital Chatbot")
    
    if not st.session_state.logged_in:
        auth_tab1, auth_tab2 = st.tabs(["Login", "Register"])
        
        with auth_tab1:
            st.subheader("Login")
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            
            if st.button("Login", key="login_btn", use_container_width=True):
                success, message = login_user(username, password)
                if success:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
        
        with auth_tab2:
            st.subheader("Register")
            new_username = st.text_input("Username", key="reg_username")
            new_password = st.text_input("Password", type="password", key="reg_password")
            confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm")
            
            if st.button("Register", key="reg_btn", use_container_width=True):
                if new_password != confirm_password:
                    st.error("Passwords don't match")
                else:
                    success, message = register_user(new_username, new_password)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
    
    else:
        # User info
        st.success(f"Welcome {st.session_state.username} !")
        
        # Navigation
        page = st.radio(
            "Select page:",
            ["Chat", "Tools"],
            label_visibility="collapsed", 
            horizontal=True
        )
        
        # Logout
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.rerun()
        st.divider()

# Main content
if not st.session_state.logged_in:
    st.markdown("""
    # 🏥 Hospital Chatbot
    
    Welcome! Please login or register to continue.
    """)
else:
    # Check backend
    if not api_client.health_check():
        st.error("⚠️ Backend is not available. Make sure it's running on http://localhost:8000")
    else:
        if page == "Chat":
            from src.pages.chat import show_chat
            show_chat()
        elif page == "Tools":
            from src.pages.tools import show_tools
            show_tools()
