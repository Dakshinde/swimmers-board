FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure JSON data files exist
RUN python -c "
import json, os
if not os.path.exists('workouts.json'):
    json.dump({}, open('workouts.json','w'))
if not os.path.exists('food_log.json'):
    json.dump({'entries':[]}, open('food_log.json','w'))
"

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "app:app"]