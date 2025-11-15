import streamlit as st
import requests

st.set_page_config(page_title="LUMEN Assistant", layout="wide")

st.title("🧠 LUMEN – Legal & Mental Health Assistant")

st.sidebar.header("Settings")
mode = st.sidebar.selectbox("Select Mode", ["Legal Assistant", "Mental Health Assistant"])

user_input = st.text_input("Ask your question:")
submit = st.button("Submit")

if submit and user_input:
    payload = {
        "query": user_input,
        "mode": "legal" if mode == "Legal Assistant" else "mental"
    }
    
    response = requests.post("http://localhost:8000/chat", json=payload)
    
    st.write("### Response:")
    st.write(response.json()["answer"])
