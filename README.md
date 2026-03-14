# Dakshinde Swim Dashboard

Minimal personal web app — swim workouts + food log + gold medal countdown.

---

## Project Structure

```
swim-dashboard/
├── app.py               # Flask backend — all routes + data logic
├── workouts.json        # Weekly workouts (keyed by weekday)
├── food_log.json        # Food entries with timestamps
├── requirements.txt     # Flask + gunicorn
├── Dockerfile           # For Render (Docker)
├── Procfile             # For Render (native) or Heroku
├── vercel.json          # For Vercel
├── templates/
│   └── index.html       # Single-page UI + inline JS
└── static/
    └── style.css        # Sky-blue light theme
```

---

## Run Locally

```bash
pip install flask
python app.py
# → http://localhost:5000
```

On phone (same WiFi): `http://<your-laptop-ip>:5000`

---

## Set Your Competition Date

Edit `app.py` lines 12–14:

```python
COMPETITION_DATE   = date(2025, 8, 15)   # ← your competition date
TRAINING_START_DATE = date(2025, 3, 1)   # ← when you started training
```

---

## Deploy on Render (Docker) — Recommended

1. Push this folder to a GitHub repo
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your repo
4. Set:
   - **Runtime**: Docker
   - **Dockerfile path**: `./Dockerfile`
   - **Port**: `5000`
5. Deploy

> ⚠️ JSON files (`workouts.json`, `food_log.json`) are written to the container's filesystem.
> On Render free tier, the filesystem resets on each deploy.
> **Workaround**: commit your `workouts.json` to git so it's always present at deploy time.
> For food log persistence, upgrade to Render's persistent disk or swap to SQLite.

---

## Deploy on Vercel

> ⚠️ Vercel runs serverless — filesystem writes don't persist between requests.
> Vercel works for **read-only** use (viewing workouts). For full write support, use Render.

```bash
npm i -g vercel
vercel login
vercel --prod
```

---

## Workout JSON format (paste into Import section)

```json
{
  "monday":    { "warmup": "200m swim", "main": "8x50 sprint", "cooldown": "100m easy" },
  "tuesday":   { "warmup": "300m mixed", "main": "4x100 threshold", "cooldown": "200m easy" },
  "wednesday": { "warmup": "REST", "main": "—", "cooldown": "—" },
  "thursday":  { "warmup": "400m easy", "main": "10x25 max sprint", "cooldown": "150m easy" },
  "friday":    { "warmup": "200m + 100m kick", "main": "6x75 descend", "cooldown": "200m" },
  "saturday":  { "warmup": "500m easy", "main": "3x200 tempo", "cooldown": "300m easy" },
  "sunday":    { "warmup": "REST", "main": "—", "cooldown": "—" }
}
```

---

## Add to Home Screen (as app)

- **iPhone**: Safari → Share → Add to Home Screen
- **Android**: Chrome → ⋮ menu → Add to Home Screen / Install App