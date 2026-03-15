from flask import Flask, render_template, request, jsonify
import json
import os
import sqlite3
from datetime import datetime, date

app = Flask(__name__)

# ── Adjust these two dates ─────────────────────────────────────────
COMPETITION_DATE    = date(2026, 8, 15)
TRAINING_START_DATE = date(2026, 3, 14)
# ──────────────────────────────────────────────────────────────────

WORKOUTS_FILE = "workouts.json"
DB_PATH = os.environ.get("DB_PATH", "swim.db")


# ── Database setup ─────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS food_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                text      TEXT    NOT NULL,
                date      TEXT    NOT NULL,
                timestamp TEXT    NOT NULL
            )
        """)
        conn.commit()


# ── Workout helpers (still JSON — workouts are pasted weekly) ──────
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
    day = datetime.now().strftime("%A")
    raw = load_workouts()
    meta = {}
    if "user" in raw:
        meta["goal"] = raw.get("goal", "")
        meta["target_protein"] = raw.get("target_protein_grams", None)
    day_data = extract_day(raw, day)
    return jsonify({"day": day, "workout": day_data, "meta": meta})


@app.route("/api/countdown")
def countdown():
    today = date.today()
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

    now = datetime.now()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO food_log (text, date, timestamp) VALUES (?, ?, ?)",
            (text, now.strftime("%Y-%m-%d"), now.isoformat())
        )
        conn.commit()

    return jsonify({"success": True, "entry": {
        "text": text,
        "timestamp": now.isoformat(),
        "date": now.strftime("%Y-%m-%d")
    }})


@app.route("/api/food-log")
def get_food_log():
    today = datetime.now().strftime("%Y-%m-%d")
    with get_db() as conn:
        rows = conn.execute(
            "SELECT text, timestamp, date FROM food_log WHERE date = ? ORDER BY id DESC",
            (today,)
        ).fetchall()
    entries = [{"text": r["text"], "timestamp": r["timestamp"], "date": r["date"]} for r in rows]
    return jsonify({"entries": entries})


@app.route("/api/summary")
def generate_summary():
    today = datetime.now().strftime("%Y-%m-%d")
    date_str = datetime.now().strftime("%A, %d %B %Y")

    # Food only from DB
    with get_db() as conn:
        rows = conn.execute(
            "SELECT text FROM food_log WHERE date = ? ORDER BY id ASC",
            (today,)
        ).fetchall()
    today_food = [r["text"] for r in rows]

    lines = ["FOOD SUMMARY", date_str, ""]
    if today_food:
        for item in today_food:
            lines.append(f"- {item}")
    else:
        lines.append("(no food logged today)")

    lines += [
        "",
        f"Total entries: {len(today_food)}",
        "",
        "Paste this into Gemini for nutrition analysis."
    ]

    return jsonify({"summary": "\n".join(lines)})


@app.route("/api/delete-food/<int:entry_id>", methods=["DELETE"])
def delete_food(entry_id):
    with get_db() as conn:
        conn.execute("DELETE FROM food_log WHERE id = ?", (entry_id,))
        conn.commit()
    return jsonify({"success": True})


if __name__ == "__main__":
    init_db()
    if not os.path.exists(WORKOUTS_FILE):
        save_workouts({})
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)


# Run init_db on every startup (safe — CREATE TABLE IF NOT EXISTS)
init_db()