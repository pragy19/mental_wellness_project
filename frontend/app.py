# frontend/app.py
import streamlit as st
import requests
import os

# CONFIG
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:5000")

st.set_page_config(page_title="SafeSpace Challenge", page_icon="🌱", layout="centered")

# --- helpers ---
def reset_state():
    keys = ["page", "answers", "stigma_level", "scenario", "ai_reflection", "ai_tip"]
    for k in keys:
        st.session_state.pop(k, None)
    st.session_state.page = "landing"

if "page" not in st.session_state:
    st.session_state.page = "landing"

# --- Landing page: reverse psychology challenge ---
if st.session_state.page == "landing":
    st.markdown("<div style='text-align:center; padding:20px;'>", unsafe_allow_html=True)
    st.title("🌱 Most people won't click this...")
    st.subheader("Think you're fine? Prove it. (Or just be curious.)")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("**No sign-up — anonymous.** Just a few minutes to check-in and try a roleplay.")
    if st.button("Take the Challenge 🚀"):
        st.session_state.page = "questions"

# --- Questions page (daily AI-generated) ---
elif st.session_state.page == "questions":
    st.header("📝 Daily Stigma Check")

    try:
        res = requests.get(f"{BACKEND_URL}/get_questions", timeout=6)
        res.raise_for_status()
        questions = res.json().get("questions", [])
    except Exception:
        st.warning("⚠️ Could not fetch today's questions. Using default set.")
        questions = [
            "Do you avoid talking about how you feel because of others?",
            "Have you felt judged for needing help with stress?",
            "Do you think admitting you struggle is weak?"
        ]

    answers = []
    for i, q in enumerate(questions):
        ans = st.radio(q, ["Yes", "Maybe", "No"], key=f"q{i}")
        answers.append(ans)

    if st.button("Submit Answers"):
        try:
            r = requests.post(f"{BACKEND_URL}/stigma_score", json={"answers": answers}, timeout=6)
            r.raise_for_status()
            stigma = r.json().get("stigma_level", "Unknown")
        except Exception:
            stigma = "Unknown"

        st.session_state.stigma_level = stigma
        st.session_state.answers = answers
        st.session_state.page = "roleplay"

# --- Roleplay page (daily scenario) ---
elif st.session_state.page == "roleplay":
    st.header("🎭 Daily Roleplay")

    try:
        r = requests.get(f"{BACKEND_URL}/get_scenario", timeout=6)
        r.raise_for_status()
        scenario = r.json().get("scenario", "")
    except Exception:
        scenario = "A friend says 'You're making a big deal of nothing' when you open up about stress. How would you reply?"

    st.write("**Scenario:**")
    st.info(scenario)
    st.session_state.scenario = scenario

    user_input = st.text_area("Type how you'd respond in this situation:", key="reply_box", height=120)

    if st.button("Get AI Feedback"):
        if not user_input.strip():
            st.warning("✍️ Please type a response before submitting.")
        else:
            payload = {
                "user_input": user_input,
                "scenario": st.session_state.scenario,
                "stigma_level": st.session_state.get("stigma_level", "Unknown")
            }
            try:
                rr = requests.post(f"{BACKEND_URL}/ask_ai", json=payload, timeout=10)
                rr.raise_for_status()
                data = rr.json()
                st.session_state.ai_reflection = data.get("ai_reflection", "")
                st.session_state.ai_tip = data.get("ai_tip", "")
                st.session_state.page = "reflection"
            except Exception:
                st.error("❌ AI feedback currently unavailable. Please try again later.")

# --- Reflection page ---
elif st.session_state.page == "reflection":
    st.header("🌟 Reflection & Suggestion")
    st.write(f"**Your stigma level:** {st.session_state.get('stigma_level', 'Unknown')}")

    st.subheader("AI Reflection")
    st.write(st.session_state.get("ai_reflection", ""))

    st.subheader("Try this")
    st.success(st.session_state.get("ai_tip", "Try a short breathing exercise: 4-4-4."))

    st.write("---")
    st.button("🔄 Restart", on_click=reset_state)

    st.caption("⚠️ If you feel in immediate danger or are thinking of self-harm, please contact local emergency services or a crisis helpline.")
