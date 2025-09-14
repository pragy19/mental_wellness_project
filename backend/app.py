import os
import datetime
import re
import tempfile
from flask import Flask, request, jsonify
import google.generativeai as genai

# --- Setup service account for Gemini / Vertex AI ---
# Store the JSON content in Railway env variable: GOOGLE_APPLICATION_CREDENTIALS_JSON
json_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
if not json_creds:
    raise ValueError("GOOGLE_APPLICATION_CREDENTIALS_JSON is not set!")

# Write the JSON to a temporary file and set GOOGLE_APPLICATION_CREDENTIALS
creds_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
creds_file.write(json_creds.encode())
creds_file.close()
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_file.name

# Configure Gemini API (no API key needed)
MODEL_NAME = "gemini-1.5-flash"

app = Flask(__name__)
daily_cache = {}  # In-memory per-day cache

# --- Helpers ---
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
        # Extract text safely
        text = getattr(response, "text", None)
        if not text and getattr(response, "candidates", None):
            text = response.candidates[0].content.parts[0].text
        return sanitize_text(text or "[AI error: empty response]")
    except Exception as e:
        print("Gemini call failed:", e)
        return f"[AI error: {e}]"

# --- Endpoints ---

@app.route("/get_questions", methods=["GET"])
def get_questions():
    today = str(datetime.date.today())
    if today not in daily_cache:
        prompt = (
            "Generate 3 short stigma-related self-reflection questions for young Indian students. "
            "Keep them easy to answer with Yes/No/Maybe. Return as a numbered list."
        )
        try:
            text = generate_with_gemini(prompt)
            print(f"[DEBUG] Gemini AI raw response:\n{text}\n")  # ✅ log AI output
            # Extract questions safely
            lines = [line.strip("0123456789. -") for line in text.splitlines() if line.strip()]
            questions = [q for q in lines if len(q) > 5][:3]

            if len(questions) < 3:
                print("[WARNING] Gemini AI returned fewer than 3 questions, using default set.")
                questions = [
                    "Do you avoid sharing feelings because of judgment?",
                    "Have you ever felt ashamed asking for mental health help?",
                    "Do you think seeking help is a weakness?"
                ]

            daily_cache[today] = {"questions": questions}

        except Exception as e:
            print(f"[ERROR] Failed to generate questions: {e}")
            questions = [
                "Do you avoid sharing feelings because of judgment?",
                "Have you ever felt ashamed asking for mental health help?",
                "Do you think seeking help is a weakness?"
            ]
            daily_cache[today] = {"questions": questions}

    return jsonify({"questions": daily_cache[today]["questions"]})


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
    if score <= 2:
        level = "Low"
    elif score <= 4:
        level = "Medium"
    else:
        level = "High"
    return jsonify({"stigma_level": level, "raw_score": score})

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

    # Parse response safely using regex
    import re
    reflection_match = re.search(r"REFLECTION\s*:\s*(.*)", ai_text, re.IGNORECASE)
    tip_match = re.search(r"TIP\s*:\s*(.*)", ai_text, re.IGNORECASE)

    reflection = reflection_match.group(1).strip() if reflection_match else "I hear you — it takes courage to share this."
    tip = tip_match.group(1).strip() if tip_match else "Try writing your thoughts in a journal for 5 minutes today."

    return jsonify({"ai_reflection": reflection, "ai_tip": tip, "raw_ai": ai_text})

# Optional root route
@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Mental Wellness AI API is running. Use /get_questions, /get_scenario, /stigma_score, /ask_ai"})

# --- Run App ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)

