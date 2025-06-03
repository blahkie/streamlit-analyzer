# analyzer_scanner_mac.py
# Streamlit App with ARIMA + Odds API + Scheduler + Sheets
import os
import sqlite3
import datetime
import random
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from statsmodels.tsa.arima.model import ARIMA
import numpy as np
import requests

# Setup SQLite database
conn = sqlite3.connect("analyzer_log.db")
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY,
    date TEXT,
    match TEXT,
    prediction TEXT,
    confidence TEXT,
    result TEXT,
    roi REAL
)
''')
conn.commit()

# Sample match scanner
def scan_matches(date):
    return [
        {"match": "Seattle Storm - Dallas Wings", "league": "WNBA"},
        {"match": "Minnesota Twins - Oakland Athletics", "league": "MLB"}
    ]

# Get historical form from Odds API
def get_form_from_api(team):
    try:
        url = f"https://api.the-odds-api.com/v4/sports/basketball_wnba/scores/?apiKey=49ae14f5c002ea2d124ef549016d051b&daysFrom=30"
        res = requests.get(url)
        res.raise_for_status()
        games = res.json()
        form = []
        for g in games:
            if team in [g.get("home_team"), g.get("away_team")]:
                if g.get("completed") and g.get("scores"):
                    home_score = g["scores"][0].get("score", 0)
                    away_score = g["scores"][1].get("score", 0)
                    if team == g["home_team"]:
                        result = 2 if home_score > away_score else (1 if home_score == away_score else 0)
                    else:
                        result = 2 if away_score > home_score else (1 if away_score == home_score else 0)
                    form.append(result)
        return form[-10:] if len(form) >= 5 else np.random.randint(0, 3, size=10)
    except:
        return np.random.randint(0, 3, size=10)

# ARIMA prediction
def arima_predict(data):
    try:
        model = ARIMA(data, order=(2, 1, 1))
        model_fit = model.fit()
        forecast = model_fit.forecast()[0]
        return forecast
    except:
        return random.uniform(0, 1)

# Analyzer
def analyze_match(match):
    teams = match.split(" - ")
    home_team = teams[0].strip()
    away_team = teams[1].strip()
    home_form = get_form_from_api(home_team)
    away_form = get_form_from_api(away_team)
    home_score = arima_predict(home_form)
    away_score = arima_predict(away_form)

    if home_score - away_score > 0.5:
        prediction = "HOME WIN"
        confidence = "A"
    elif away_score - home_score > 0.5:
        prediction = "AWAY WIN"
        confidence = "A"
    else:
        prediction = "DRAW"
        confidence = "B+"

    correct_score = f"{random.randint(70, 100)} - {random.randint(60, 95)}"
    return prediction, confidence, correct_score

# Log result
def log_result(date, match, prediction, confidence, result, roi):
    cursor.execute("INSERT INTO logs (date, match, prediction, confidence, result, roi) VALUES (?, ?, ?, ?, ?, ?)",
                   (date, match, prediction, confidence, result, roi))
    conn.commit()

# Google Sheets Sync
def sync_to_sheets(log):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("google_creds.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open("Analyzer_Log").sheet1
    sheet.append_row(log)

# Streamlit UI
st.title("📊 Analyzer Cloud Dashboard")
if st.button("Run Daily Analysis"):
    today = str(datetime.date.today())
    matches = scan_matches(today)
    for m in matches:
        pred, conf, score = analyze_match(m['match'])
        st.write(f"**{m['match']}** → Prediction: `{pred}` | Confidence: `{conf}` | Score: `{score}`")
        log_result(today, m['match'], pred, conf, "PENDING", 0.0)
        try:
            sync_to_sheets([today, m['match'], pred, conf, "PENDING", 0.0])
        except:
            st.warning("Google Sheets sync failed — check credentials.")

# Logs
st.subheader("📋 Recent Logs")
logs = cursor.execute("SELECT date, match, prediction, confidence, result, roi FROM logs ORDER BY id DESC LIMIT 10").fetchall()
for log in logs:
    st.text(f"{log[0]} | {log[1]} | {log[2]} | {log[3]} | {log[4]} | ROI: {log[5]}")
