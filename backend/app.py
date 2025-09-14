import os
import datetime
import re
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables (if using .env)
load_dotenv()

# Set Gemini API key (get from https://aistudio.google.com/app/apikey)
API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_API_KEY_HERE")
genai.configure(api_key=API_KEY)

# Model selection
MODEL_NAME = "gemini-1.5-flash"

app = Flask(__name__)

# Simple in-memory cache (per day)
daily_cache = {}

# Sanitizer helper
def sanitize_text(text, max_len=800):
    if not text:
        return ""
    text = text.strip()
    if len(text) > max_len:
        text = text[:max_len]
    text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', ' ', text)
    return text

def generate_with_gemini(prompt, max_output_tokens=200):
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(prompt)
        return sanitize_text(response.text)
    except Exception as e:
        print("Gemini call failed:", e)
        return "[AI error: unable to generate text right now]"

# --- Endpoints ---

# Daily questions
@app.route("/get_questions", methods=["GET"])
def get_questions():
    today = str(datetime.date.today())
    if today not in daily_cache:
        prompt = (
            "Generate 3 short stigma-related self-reflection questions for young Indian students. "
            "Keep them easy to answer with Yes/No/Maybe. Return as a numbered list."
        )
        text = generate_with_gemini(prompt)
        lines = [line.strip("0123456789. -") for line in text.splitlines() if line.strip()]
        questions = [q for q in lines if len(q) > 5][:3]
        if len(questions) < 3:
            questions = [
                "Do you avoid sharing feelings because of judgment?",
                "Have you ever felt ashamed asking for mental health help?",
                "Do you think seeking help is a weakness?"
            ]
        daily_cache[today] = {"questions": questions}
    return jsonify({"questions": daily_cache[today]["questions"]})

# Daily scenario
@app.route("/get_scenario", methods=["GET"])
def get_scenario():
    today = str(datetime.date.today())
    key = f"scenario-{today}"
    if key not in daily_cache:
        prompt = (
            "Write one realistic roleplay scenario (2-3 sentences) of an Indian college student "
            "facing stigma about mental health."
        )
        text = generate_with_gemini(prompt)
        scenario = text.strip().splitlines()[0] if text.strip() else ""
        if not scenario:
            scenario = "In a group study, a friend says 'You are just lazy' when you mention stress."
        daily_cache[key] = {"scenario": scenario}
    return jsonify({"scenario": daily_cache[key]["scenario"]})

# Compute stigma score
@app.route("/stigma_score", methods=["POST"])
def stigma_score():
    data = request.get_json() or {}
    answers = data.get("answers", [])
    score = 0
    for a in answers:
        s = str(a).lower()
        if s in ("yes", "often", "always", "agree", "defend"):
            score += 2
        elif s in ("maybe", "sometimes"):
            score += 1
        else:
            score += 0
    if score <= 2:
        level = "Low"
    elif score <= 4:
        level = "Medium"
    else:
        level = "High"
    return jsonify({"stigma_level": level, "raw_score": score})

# Ask AI for feedback
@app.route("/ask_ai", methods=["POST"])
def ask_ai():
    data = request.get_json() or {}
    user_reply = sanitize_text(data.get("user_input", ""))
    scenario = sanitize_text(data.get("scenario", ""))
    stigma_level = data.get("stigma_level", "Unknown")

    prompt = (
        "You are an empathetic counselor bot for Indian youth.\n\n"
        f"Scenario: {scenario}\n"
        f"User response: {user_reply}\n"
        f"Stigma level: {stigma_level}\n\n"
        "TASK:\n"
        "1) Provide a short empathetic reflection (1-2 sentences).\n"
        "2) Offer one simple coping tip (1 sentence).\n"
        "3) If distress or self-harm is detected, advise seeking immediate help + give India helpline: Vandrevala 1860 2662 345.\n"
        "Return as:\nREFLECTION: ...\nTIP: ..."
    )

    ai_text = generate_with_gemini(prompt)
    reflection, tip = "", ""
    for line in ai_text.splitlines():
        if line.lower().startswith("reflection"):
            reflection = line.split(":", 1)[1].strip()
        elif line.lower().startswith("tip"):
            tip = line.split(":", 1)[1].strip()
    if not reflection:
        reflection = "I hear you — it takes courage to share this."
    if not tip:
        tip = "Try writing your thoughts in a journal for 5 minutes today."

    return jsonify({"ai_reflection": reflection, "ai_tip": tip, "raw_ai": ai_text})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
