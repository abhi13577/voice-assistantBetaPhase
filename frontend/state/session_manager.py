import uuid
import streamlit as st

def init_session():

    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = str(uuid.uuid4())

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "latency" not in st.session_state:
        st.session_state.latency = 0