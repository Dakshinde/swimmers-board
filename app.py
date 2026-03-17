from flask import Flask, render_template, request, jsonify
import json
import os
import csv
import io
from datetime import datetime, date, timezone, timedelta
from pymongo import MongoClient
from pymongo.server_api import ServerApi

app = Flask(__name__)

# ── Dates ──────────────────────────────────────────────────────────
COMPETITION_DATE    = date(2026, 8, 15)
TRAINING_START_DATE = date(2026, 3, 14)

# ── IST timezone (UTC+5:30) ────────────────────────────────────────
IST = timezone(timedelta(hours=5, minutes=30))

def now_ist():
    return datetime.now(IST)

# ── MongoDB ────────────────────────────────────────────────────────
MONGO_URI = os.environ.get("MONGO_URI", "")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI env variable not set. Add it in Railway Variables.")

client = MongoClient(MONGO_URI, server_api=ServerApi("1"))
db = client["swim_dashboard"]
food_col  = db["food_log"]
notes_col = db["notes"]

# ── Workouts ───────────────────────────────────────────────────────
WORKOUTS_FILE = "workouts.json"

def load_workouts():
    if not os.path.exists(WORKOUTS_FILE):
        return {}
    with open(WORKOUTS_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_workouts(data):
    with open(WORKOUTS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def extract_day(raw_data, day_name):
    if "week_plan" in raw_data:
        for entry in raw_data["week_plan"]:
            if entry.get("day", "").lower() == day_name.lower():
                return entry
        return None
    return raw_data.get(day_name.lower(), None)


# ── Routes ─────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/today-workout")
def today_workout():
    day = now_ist().strftime("%A")
    raw = load_workouts()
    meta = {}
    if "athlete" in raw:
        meta["goal"] = raw.get("goal", "")
        meta["target_protein"] = None
    elif "user" in raw:
        meta["goal"] = raw.get("goal", "")
        meta["target_protein"] = raw.get("target_protein_grams", None)
    day_data = extract_day(raw, day)
    return jsonify({"day": day, "workout": day_data, "meta": meta})


@app.route("/api/countdown")
def countdown():
    today = now_ist().date()
    days_left = max(0, (COMPETITION_DATE - today).days)
    total_days = (COMPETITION_DATE - TRAINING_START_DATE).days
    days_done = max(0, min((today - TRAINING_START_DATE).days, total_days))
    return jsonify({
        "days_left": days_left,
        "days_done": days_done,
        "total_days": total_days,
        "competition_date": COMPETITION_DATE.strftime("%d %b %Y"),
    })


@app.route("/api/import-workout", methods=["POST"])
def import_workout():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400
        save_workouts(data)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/log-food", methods=["POST"])
def log_food():
    data = request.get_json()
    text = data.get("entry", "").strip()
    if not text:
        return jsonify({"error": "Empty entry"}), 400

    now = now_ist()
    entry = {
        "text": text,
        "date": now.strftime("%Y-%m-%d"),
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "time_display": now.strftime("%I:%M %p"),
    }
    result = food_col.insert_one(entry)
    return jsonify({"success": True, "entry": {
        "id": str(result.inserted_id),
        "text": text,
        "timestamp": entry["timestamp"],
        "time_display": entry["time_display"],
        "date": entry["date"],
    }})


@app.route("/api/food-log")
def get_food_log():
    today = now_ist().strftime("%Y-%m-%d")
    rows = list(food_col.find(
        {"date": today},
        {"_id": 1, "text": 1, "timestamp": 1, "time_display": 1, "date": 1}
    ).sort("timestamp", -1))
    entries = [{
        "id": str(r["_id"]),
        "text": r["text"],
        "timestamp": r.get("timestamp", ""),
        "time_display": r.get("time_display", r.get("timestamp", "")[-8:-3] if r.get("timestamp") else ""),
        "date": r["date"]
    } for r in rows]
    return jsonify({"entries": entries})


@app.route("/api/summary")
def generate_summary():
    today = now_ist().strftime("%Y-%m-%d")
    date_str = now_ist().strftime("%A, %d %B %Y")

    rows = list(food_col.find({"date": today}, {"text": 1, "time_display": 1}).sort("timestamp", 1))
    today_food = [(r["text"], r.get("time_display", "")) for r in rows]

    lines = ["FOOD SUMMARY", date_str, ""]
    if today_food:
        for i, (item, t) in enumerate(today_food, 1):
            lines.append(f"{i}. [{t}] {item}")
    else:
        lines.append("(no food logged today)")

    lines += ["", f"Total entries: {len(today_food)}", "", "Paste into Gemini for nutrition analysis."]
    return jsonify({"summary": "\n".join(lines)})


# ── Notes ──────────────────────────────────────────────────────────
@app.route("/api/add-note", methods=["POST"])
def add_note():
    data = request.get_json()
    text = data.get("text", "").strip()
    tag  = data.get("tag", "general").strip()
    if not text:
        return jsonify({"error": "Empty note"}), 400

    now = now_ist()
    note = {
        "text": text,
        "tag": tag,
        "date": now.strftime("%Y-%m-%d"),
        "date_display": now.strftime("%d %b %Y"),
        "time_display": now.strftime("%I:%M %p"),
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    result = notes_col.insert_one(note)
    note["id"] = str(result.inserted_id)
    return jsonify({"success": True, "note": note})


@app.route("/api/notes")
def get_notes():
    rows = list(notes_col.find(
        {}, {"_id": 1, "text": 1, "tag": 1, "date": 1,
             "date_display": 1, "time_display": 1, "timestamp": 1}
    ).sort("timestamp", -1).limit(50))
    notes = [{
        "id": str(r["_id"]),
        "text": r["text"],
        "tag": r.get("tag", "general"),
        "date": r.get("date", ""),
        "date_display": r.get("date_display", ""),
        "time_display": r.get("time_display", ""),
        "timestamp": r.get("timestamp", ""),
    } for r in rows]
    return jsonify({"notes": notes})


@app.route("/api/delete-note/<note_id>", methods=["DELETE"])
def delete_note(note_id):
    from bson import ObjectId
    notes_col.delete_one({"_id": ObjectId(note_id)})
    return jsonify({"success": True})


@app.route("/api/export/food.csv")
def export_csv():
    rows = list(food_col.find({}, {"_id": 0, "date": 1, "timestamp": 1, "text": 1}).sort("timestamp", 1))
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "timestamp", "food"])
    for r in rows:
        writer.writerow([r.get("date"), r.get("timestamp"), r.get("text")])
    from flask import Response
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=food_log.csv"})


@app.route("/api/debug/food")
def debug_food():
    rows = list(food_col.find({}, {"_id": 0}).sort("timestamp", -1).limit(20))
    return jsonify(rows)


if __name__ == "__main__":
    if not os.path.exists(WORKOUTS_FILE):
        save_workouts({})
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)