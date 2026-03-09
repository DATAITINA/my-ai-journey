import os
from pathlib import Path
from typing import Optional
import streamlit as st
from google import genai
from google.genai import types
from dotenv import load_dotenv

SYSTEM_PROMPT = (
    "You are a cheerful AI assistant built as a birthday gift for Favour. "
    "Be positive, friendly, playful, and supportive."
)

DEFAULT_MODEL = "gemini-2.5-flash-lite"

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")


st.set_page_config(
    page_title="Favour AI ✨",
    page_icon="🎂",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;700&family=DM+Sans:wght@300;400;500&display=swap');

      :root {
        --rose:    #e8635a;
        --rose-lt: #fde8e6;
        --sand:    #faf6f1;
        --ink:     #1c1714;
        --muted:   #8a7d77;
        --border:  #ede5df;
        --card:    #ffffff;
        --radius:  20px;
        --shadow:  0 8px 32px rgba(28,23,20,.08);
      }

      /* ── Reset & base ── */
      html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
        background: var(--sand) !important;
        color: var(--ink);
      }
      .stApp { background: var(--sand) !important; }

      /* subtle radial blobs */
      .stApp::before {
        content: '';
        position: fixed; inset: 0; pointer-events: none; z-index: 0;
        background:
          radial-gradient(ellipse 60% 50% at 5% 0%,  rgba(232,99,90,.12) 0%, transparent 70%),
          radial-gradient(ellipse 50% 45% at 95% 5%,  rgba(255,210,180,.25) 0%, transparent 65%),
          radial-gradient(ellipse 45% 40% at 90% 95%, rgba(230,195,215,.20) 0%, transparent 65%);
      }

      /* ── Container ── */
      .block-container {
        position: relative; z-index: 1;
        max-width: 820px !important;
        padding: 2rem 1.5rem 4rem !important;
      }

      /* ── Header banner ── */
      .favour-header {
        display: flex;
        align-items: stretch;
        gap: 16px;
        margin-bottom: 28px;
      }
      .favour-main-card {
        flex: 1.4;
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 26px 28px 22px;
        box-shadow: var(--shadow);
      }
      .favour-main-card .eyebrow {
        font-size: 10px;
        letter-spacing: 3.5px;
        text-transform: uppercase;
        color: var(--rose);
        font-weight: 500;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 6px;
      }
      .favour-main-card h1 {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 36px;
        font-weight: 700;
        margin: 0 0 8px;
        line-height: 1.15;
        color: var(--ink);
      }
      .favour-main-card p {
        margin: 0;
        color: var(--muted);
        font-size: 14px;
        line-height: 1.55;
        font-weight: 300;
      }
      .favour-side-card {
        flex: 1;
        background: linear-gradient(145deg, #fff5f4 0%, #fff9f5 100%);
        border: 1px solid rgba(232,99,90,.22);
        border-radius: var(--radius);
        padding: 22px 20px;
        box-shadow: var(--shadow);
      }
      .favour-side-card h3 {
        font-family: 'Playfair Display', serif;
        font-size: 17px;
        margin: 0 0 12px;
        color: var(--ink);
      }
      .favour-side-card .pill-list {
        display: flex;
        flex-direction: column;
        gap: 7px;
      }
      .favour-side-card .pill {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 13px;
        color: var(--muted);
        font-weight: 400;
      }
      .favour-side-card .pill span.dot {
        width: 6px; height: 6px;
        border-radius: 50%;
        background: var(--rose);
        flex-shrink: 0;
      }

      /* ── Chat messages ── */
      /* hide default avatars completely */
      div[data-testid="stChatMessageAvatarAssistant"],
      div[data-testid="stChatMessageAvatarUser"],
      [data-testid="stChatMessage"] [data-testid="chatAvatarIcon-user"],
      [data-testid="stChatMessage"] [data-testid="chatAvatarIcon-assistant"] {
        display: none !important;
      }

      div[data-testid="stChatMessage"] {
        padding: 0 !important;
        margin-bottom: 10px !important;
        gap: 0 !important;
        background: transparent !important;
        border: none !important;
      }

      /* assistant bubble */
      div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) div[data-testid="stChatMessageContent"],
      div[data-testid="stChatMessage"].assistant-message div[data-testid="stChatMessageContent"] {
        background: var(--card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 18px 18px 18px 4px !important;
      }

      div[data-testid="stChatMessageContent"] {
        background: var(--card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 18px !important;
        padding: 12px 16px !important;
        font-size: 14.5px !important;
        line-height: 1.6 !important;
        box-shadow: 0 2px 10px rgba(28,23,20,.05) !important;
        max-width: 88% !important;
      }

      /* ── Chat input ── */
      .stChatInput > div {
        border-radius: 999px !important;
        border: 1.5px solid var(--border) !important;
        background: var(--card) !important;
        box-shadow: 0 4px 20px rgba(28,23,20,.07) !important;
        padding: 4px 6px 4px 16px !important;
        transition: border-color .2s, box-shadow .2s;
      }
      .stChatInput > div:focus-within {
        border-color: var(--rose) !important;
        box-shadow: 0 0 0 3px rgba(232,99,90,.18) !important;
      }
      .stChatInput textarea {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        font-family: 'DM Sans', sans-serif !important;
        font-size: 14px !important;
        color: var(--ink) !important;
        padding: 10px 0 !important;
        resize: none !important;
      }
      .stChatInput textarea::placeholder { color: #c2b4ad !important; }
      .stChatInput button {
        border-radius: 50% !important;
        background: var(--rose) !important;
        color: white !important;
        width: 40px !important; height: 40px !important;
        box-shadow: 0 6px 16px rgba(232,99,90,.35) !important;
        border: none !important;
        transition: transform .15s, box-shadow .15s;
      }
      .stChatInput button:hover {
        transform: scale(1.06) !important;
        box-shadow: 0 8px 22px rgba(232,99,90,.45) !important;
      }

      /* ── Spinner ── */
      .stSpinner > div { border-top-color: var(--rose) !important; }

      /* ── Scrollbar ── */
      ::-webkit-scrollbar { width: 5px; }
      ::-webkit-scrollbar-track { background: transparent; }
      ::-webkit-scrollbar-thumb { background: #ddd4ce; border-radius: 99px; }

      /* ── Mobile ── */
      @media (max-width: 640px) {
        .favour-header { flex-direction: column; }
        .favour-main-card h1 { font-size: 28px; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="favour-header">
      <div class="favour-main-card">
        <div class="eyebrow">🎂 &nbsp;Birthday Bot</div>
        <h1>Favour AI</h1>
        <p>A warm, playful assistant designed to celebrate Favour with kindness, joy, and gentle encouragement.</p>
      </div>
      <div class="favour-side-card">
        <h3>Made for Favour 🌸</h3>
        <div class="pill-list">
          <div class="pill"><span class="dot"></span>Friendly, lighthearted replies</div>
          <div class="pill"><span class="dot"></span>Encouragement whenever she needs it</div>
          <div class="pill"><span class="dot"></span>Occasional jokes, always respectful</div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ── API helpers ───────────────────────────────────────────────────────────────
def get_api_key() -> Optional[str]:
    if "GEMINI_API_KEY" in st.secrets:
        return str(st.secrets["GEMINI_API_KEY"]).strip()
    env_value = os.getenv("GEMINI_API_KEY")
    return env_value.strip() if env_value else None


def get_model() -> str:
    if "GEMINI_MODEL" in st.secrets:
        return str(st.secrets["GEMINI_MODEL"]).strip()
    env_value = os.getenv("GEMINI_MODEL")
    return env_value.strip() if env_value else DEFAULT_MODEL


def generate_reply(user_message: str) -> str:
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=get_model(),
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.8,
            max_output_tokens=300,
        ),
    )
    reply_text = (response.text or "").strip()
    if not reply_text:
        reply_text = "I might be out of words. Want to try that again? 😊"
    return reply_text


# ── Chat state ────────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Hi Favour! 🎉 I'm your birthday AI, here to cheer you on every step of the way!",
        }
    ]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("Type something kind...")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            with st.spinner(""):
                reply = generate_reply(prompt)
        except Exception as exc:
            reply = f"Sorry, I ran into a hiccup: {exc}"
        st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})