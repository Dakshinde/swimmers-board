from flask import Flask, render_template, request, jsonify
import json
import os
from datetime import datetime, date

app = Flask(__name__)

WORKOUTS_FILE = "workouts.json"
FOOD_LOG_FILE = "food_log.json"

# ── Adjust these two dates ────────────────────────────────────────
COMPETITION_DATE    = date(2025, 8, 15)   # your competition
TRAINING_START_DATE = date(2025, 3, 1)    # when you started
# ─────────────────────────────────────────────────────────────────


def load_json(filepath):
    if not os.path.exists(filepath):
        return {}
    with open(filepath, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_json(filepath, data):
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def extract_day(raw_data, day_name):
    """
    Supports two formats:
    1. Gemini rich format: { "week_plan": [ { "day": "Monday", ... } ] }
    2. Simple flat format: { "monday": { "warmup": "...", ... } }
    """
    if "week_plan" in raw_data:
        for entry in raw_data["week_plan"]:
            if entry.get("day", "").lower() == day_name.lower():
                return entry
        return None
    return raw_data.get(day_name.lower(), None)


def flatten_for_summary(day_data):
    """Turn a workout dict into plain text lines for the daily summary."""
    if not day_data:
        return ["(no workout for today)"]

    lines = []
    if "focus" in day_data:
        lines.append(f"Focus: {day_data['focus']}")

    swim = day_data.get("swim_session")
    if swim and isinstance(swim, dict):
        lines.append("SWIM SESSION:")
        for k, v in swim.items():
            lines.append(f"  {k.replace('_', ' ').title()}: {v}")
    elif swim and isinstance(swim, str):
        lines.append(f"Swim: {swim}")

    dryland = day_data.get("dryland")
    if dryland and isinstance(dryland, dict):
        lines.append("DRYLAND:")
        for k, v in dryland.items():
            lines.append(f"  {k.replace('_', ' ').title()}: {v}")
    elif dryland and isinstance(dryland, str):
        lines.append(f"Dryland: {dryland}")

    if "cardio_commute" in day_data:
        lines.append(f"Commute: {day_data['cardio_commute']}")

    if "diet_type" in day_data:
        lines.append(f"Diet: {day_data['diet_type']}")

    return lines


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/today-workout")
def today_workout():
    day = datetime.now().strftime("%A")   # e.g. "Monday"
    raw = load_json(WORKOUTS_FILE)

    meta = {}
    if "user" in raw:
        meta["goal"] = raw.get("goal", "")
        meta["target_protein"] = raw.get("target_protein_grams", None)

    day_data = extract_day(raw, day)
    return jsonify({"day": day, "workout": day_data, "meta": meta})


@app.route("/api/countdown")
def countdown():
    today = date.today()
    days_left = (COMPETITION_DATE - today).days
    total_days = (COMPETITION_DATE - TRAINING_START_DATE).days
    days_done = (today - TRAINING_START_DATE).days
    days_done = max(0, min(days_done, total_days))
    days_left = max(0, days_left)
    return jsonify({
        "days_left": days_left,
        "days_done": days_done,
        "total_days": total_days,
        "competition_date": COMPETITION_DATE.strftime("%d %b %Y"),
        "competition_name": "Gold Medal Target"
    })


@app.route("/api/import-workout", methods=["POST"])
def import_workout():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400
        save_json(WORKOUTS_FILE, data)
        return jsonify({"success": True, "message": "Workouts saved."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/log-food", methods=["POST"])
def log_food():
    data = request.get_json()
    entry_text = data.get("entry", "").strip()
    if not entry_text:
        return jsonify({"error": "Empty entry"}), 400

    food_log = load_json(FOOD_LOG_FILE)
    if "entries" not in food_log:
        food_log["entries"] = []

    entry = {
        "text": entry_text,
        "timestamp": datetime.now().isoformat(),
        "date": datetime.now().strftime("%Y-%m-%d"),
    }
    food_log["entries"].append(entry)
    save_json(FOOD_LOG_FILE, food_log)
    return jsonify({"success": True, "entry": entry})


@app.route("/api/food-log")
def get_food_log():
    food_log = load_json(FOOD_LOG_FILE)
    entries = food_log.get("entries", [])
    today = datetime.now().strftime("%Y-%m-%d")
    today_entries = [e for e in entries if e.get("date") == today]
    return jsonify({"entries": list(reversed(today_entries))})


@app.route("/api/summary")
def generate_summary():
    day = datetime.now().strftime("%A")
    raw = load_json(WORKOUTS_FILE)
    day_data = extract_day(raw, day)

    food_log = load_json(FOOD_LOG_FILE)
    entries = food_log.get("entries", [])
    today = datetime.now().strftime("%Y-%m-%d")
    today_food = [e["text"] for e in entries if e.get("date") == today]

    date_str = datetime.now().strftime("%A, %d %B %Y")
    lines = ["DAILY TRAINING SUMMARY", date_str, ""]

    lines.append("FOOD:")
    if today_food:
        for item in today_food:
            lines.append(f"  {item}")
    else:
        lines.append("  (no entries logged)")

    lines.append("")
    lines.append("WORKOUT:")
    for l in flatten_for_summary(day_data):
        lines.append(f"  {l}")

    return jsonify({"summary": "\n".join(lines)})


if __name__ == "__main__":
    if not os.path.exists(WORKOUTS_FILE):
        save_json(WORKOUTS_FILE, {})
    if not os.path.exists(FOOD_LOG_FILE):
        save_json(FOOD_LOG_FILE, {"entries": []})
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)