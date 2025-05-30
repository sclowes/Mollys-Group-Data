from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime, time, timedelta
import sqlite3

app = Flask(__name__)
DB_PATH = 'database.db'

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS entries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT,
                        time_slot TEXT,
                        admits INTEGER,
                        left INTEGER,
                        holding INTEGER,
                        timestamp TEXT
                    )''')
        conn.commit()

def get_night_start(target_datetime):
    if target_datetime.time() < time(6, 0):
        target_datetime -= timedelta(days=1)
    return target_datetime.date()

def calculate_holding_for(date_str):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT SUM(admits), SUM(left) FROM entries WHERE date = ?", (date_str,))
        result = c.fetchone()
        total_admits = result[0] or 0
        total_left = result[1] or 0
        return total_admits - total_left

@app.route('/')
def index():
    return redirect(url_for('submit_entry'))

@app.route('/submit', methods=['GET', 'POST'])
def submit_entry():
    times = [f"{h:02}:{m:02}" for h in range(15, 24) for m in (0, 30)] + [f"{h:02}:{m:02}" for h in range(0, 7) for m in (0, 30)]

    if request.method == 'POST':
        admits = int(request.form['admits'])
        left = int(request.form['left'])
        time_slot = request.form['time_slot']

        now = datetime.now()
        night_start_date = get_night_start(now)
        holding = calculate_holding_for(night_start_date.isoformat()) + admits - left

        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO entries (date, time_slot, admits, left, holding, timestamp)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (night_start_date.isoformat(), time_slot, admits, left, holding, now.isoformat()))
            conn.commit()

        return redirect(url_for('submit_entry'))

    return render_template('submit.html', times=times)

@app.route('/view', methods=['GET', 'POST'])
def view_entries():
    rows = []
    selected_date = None

    if request.method == 'POST':
        selected_date = request.form['date']
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT time_slot, admits, left, holding FROM entries WHERE date = ? ORDER BY time_slot", (selected_date,))
            rows = c.fetchall()

    return render_template('view.html', rows=rows, selected_date=selected_date)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8000)
