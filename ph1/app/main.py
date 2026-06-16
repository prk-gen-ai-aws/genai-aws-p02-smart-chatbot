"""
Project 2 — Smart Q&A Chatbot
Streamlit UI — 4 pages
"""

import streamlit as st
import requests
import uuid
import json
import os
from dotenv import load_dotenv

load_dotenv()

# ── Config ──
API_GATEWAY_URL = os.getenv('API_GATEWAY_URL')

# ── Page config ──
st.set_page_config(
    page_title="Smart Q&A Chatbot",
    page_icon="💬",
    layout="wide"
)

# ── Initialize session state ──
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if 'messages' not in st.session_state:
    st.session_state.messages = []

# ── Sidebar navigation ──
st.sidebar.title("💬 Smart Chatbot")
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "Navigate",
    ["Chat", "How it works", "Architecture", "About"]
)
st.sidebar.markdown("---")
st.sidebar.caption(f"Session: {st.session_state.session_id[:8]}...")
st.sidebar.caption("Built on AWS · Powered by Amazon Bedrock")

# ============================================================
# PAGE 1: CHAT
# ============================================================
if page == "Chat":
    st.title("💬 Smart Q&A Chatbot")
    st.markdown("Ask me anything — I remember our conversation.")
    st.markdown("---")

    # Clear conversation button
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("Clear conversation", type="secondary"):
            st.session_state.messages = []
            st.session_state.session_id = str(uuid.uuid4())
            st.rerun()

    # Display conversation history
    chat_container = st.container()
    with chat_container:
        if not st.session_state.messages:
            st.info("👋 Start a conversation by typing a message below.")
        else:
            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

    # Chat input
    user_input = st.chat_input("Ask me anything...")

    if user_input:
        # Display user message immediately
        st.session_state.messages.append({
            "role": "user",
            "content": user_input
        })

        with st.spinner("Thinking..."):
            try:
                payload = {
                    "session_id": st.session_state.session_id,
                    "message": user_input
                }
                response = requests.post(
                    API_GATEWAY_URL,
                    json=payload,
                    timeout=30
                )
                result = response.json()

                if isinstance(result, dict) and 'body' in result:
                    body = result['body']
                    if isinstance(body, str):
                        body = json.loads(body)
                else:
                    body = result

                if 'response' in body:
                    assistant_message = body['response']
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": assistant_message
                    })
                elif 'error' in body:
                    st.error(f"⚠️ Error: {body['error']}")
                    st.session_state.messages.pop()

            except requests.exceptions.Timeout:
                st.error("⏱️ Request timed out. Please try again.")
                st.session_state.messages.pop()
            except requests.exceptions.ConnectionError:
                st.error("🔌 Could not connect to the API. Please check your connection.")
                st.session_state.messages.pop()
            except Exception as e:
                st.error(f"⚠️ Something went wrong: {str(e)}")
                st.session_state.messages.pop()

        st.rerun()

# ============================================================
# PAGE 2: HOW IT WORKS
# ============================================================
elif page == "How it works":
    st.title("How it works")
    st.markdown("---")

    st.markdown("""
    This chatbot uses a fully serverless pipeline on AWS with conversation memory.
    Here is what happens when you send a message:
    """)

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("### Step 1 — Send message")
        st.markdown("""
        Your message is sent from Streamlit to **API Gateway** via a POST request.
        A unique session ID (generated when you open the app) is included with every message.
        """)

        st.markdown("### Step 2 — Read memory")
        st.markdown("""
        **AWS Lambda** reads your conversation history from **Amazon DynamoDB**
        using your session ID. This gives the AI context about what you discussed earlier.
        """)

        st.markdown("### Step 3 — Think")
        st.markdown("""
        Lambda sends your full conversation history to **Amazon Bedrock** (Claude Haiku 4.5).
        The AI reads the entire conversation before generating a response —
        this is what makes it feel like it remembers you.
        """)

    with col2:
        st.markdown("### Step 4 — Save memory")
        st.markdown("""
        The AI response is appended to your conversation history and saved back
        to **DynamoDB**. Sessions expire automatically after 24 hours via TTL.
        Only the last 10 messages are kept (sliding window) to manage costs.
        """)

        st.markdown("### Step 5 — Return")
        st.markdown("""
        The response travels back through API Gateway to Streamlit
        and is displayed in the chat interface.
        """)

        st.markdown("### Session isolation")
        st.markdown("""
        Every browser session gets a unique ID. Two users chatting simultaneously
        have completely separate conversations — they never see each other's messages.
        """)

    st.markdown("---")
    st.markdown("### Tech stack")
    cols = st.columns(4)
    with cols[0]:
        st.metric("Frontend", "Streamlit")
        st.metric("Memory", "DynamoDB")
    with cols[1]:
        st.metric("API", "API Gateway")
        st.metric("Session TTL", "24 hours")
    with cols[2]:
        st.metric("AI", "Claude Haiku 4.5")
        st.metric("Max messages", "10")
    with cols[3]:
        st.metric("Compute", "Lambda")
        st.metric("Config", "SSM")

# ============================================================
# PAGE 3: ARCHITECTURE
# ============================================================
elif page == "Architecture":
    st.title("Architecture")
    st.markdown("---")

    st.markdown("""
    ### Serverless Chatbot with Session Memory

    Fully serverless architecture on AWS. All infrastructure
    provisioned as code using **Terraform** and **CloudFormation**.
    """)

    st.info("📐 Architecture diagram: v1/docs/architecture-v1.png (coming soon)")

    st.markdown("---")
    st.markdown("### Component breakdown")

    components = {
        "Streamlit": "Python chat UI. Runs locally. Generates session UUID on load. Displays conversation history.",
        "API Gateway": "Managed REST endpoint. Routes POST /chat to Lambda. Handles HTTPS.",
        "AWS Lambda": "Serverless orchestrator. Reads session from DynamoDB, calls Bedrock, saves updated session.",
        "Amazon DynamoDB": "NoSQL session store. Partition key: session_id. TTL: 24 hours. Sliding window: last 10 messages.",
        "Amazon Bedrock": "Managed AI service running Claude Haiku 4.5. Receives full conversation history per request.",
        "SSM Parameter Store": "Stores the Bedrock model ID. Change model without touching code.",
        "IAM Role": "Least-privilege execution role. Lambda gets DynamoDB read/write, Bedrock invoke, SSM read.",
        "Terraform + CloudFormation": "All infrastructure as code. Reproducible on any AWS account."
    }

    for component, description in components.items():
        with st.expander(f"**{component}**"):
            st.markdown(description)

# ============================================================
# PAGE 4: ABOUT
# ============================================================
elif page == "About":
    st.title("About this project")
    st.markdown("---")

    st.markdown("### Gen AI on AWS — Portfolio Project")
    st.markdown("[View on GitHub](https://github.com/prk-gen-ai-aws/genai-aws-p02-smart-chatbot)")
    st.markdown("---")
    st.markdown("""
    Part of an ongoing series exploring Gen AI on AWS — applying
    real-world architecture patterns from serverless foundations
    to multi-agent agentic systems.

    Built with real-world practices:
    - **IaC** — Terraform + CloudFormation
    - **Least-privilege IAM** — Lambda only has what it needs
    - **Serverless-first** — cost-effective on a personal AWS account
    - **Fork-friendly** — clone, fill one file, run one command
    """)

    st.markdown("---")
    st.markdown("### What this project demonstrates")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **Cloud Architecture:**
        - Serverless stateful design
        - DynamoDB for session persistence
        - API Gateway + Lambda integration
        - SSM for centralized configuration
        """)
    with col2:
        st.markdown("""
        **Gen AI Engineering:**
        - Multi-turn conversation management
        - Context window handling (sliding window)
        - Session isolation per user
        - Model-agnostic design via SSM
        """)

    st.markdown("---")
    st.markdown("### Things to consider at scale")
    st.markdown("""
    | Concern | Consideration |
    |---|---|
    | **Security** | API keys or Cognito for user authentication, VPC endpoints for Bedrock |
    | **Scalability** | DynamoDB auto-scales, Lambda concurrency limits, Bedrock quota increases |
    | **High Availability** | Multi-region DynamoDB global tables, Lambda retry with backoff |
    | **Cost** | DynamoDB on-demand pricing, prompt caching, session TTL to limit storage |
    """)
