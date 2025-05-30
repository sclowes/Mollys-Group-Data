from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime, time, timedelta
import psycopg2
import os

app = Flask(__name__)
DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute('''CREATE TABLE IF NOT EXISTS entries (
                            id SERIAL PRIMARY KEY,
                            date TEXT,
                            time_slot TEXT,
                            admits INTEGER,
                            left_count INTEGER,
                            holding INTEGER,
                            timestamp TEXT
                        )''')
            conn.commit()

def get_night_start(target_datetime):
    if target_datetime.time() < time(6, 0):
        target_datetime -= timedelta(days=1)
    return target_datetime.date()

def calculate_holding_for(date_str):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT SUM(admits), SUM(left_count) FROM entries WHERE date = %s", (date_str,))
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
        left = int(request.form['left_count'])
        time_slot = request.form['time_slot']

        now = datetime.now()
        night_start_date = get_night_start(now)
        holding = calculate_holding_for(night_start_date.isoformat()) + admits - left

        with get_connection() as conn:
            with conn.cursor() as c:
                c.execute('''INSERT INTO entries (date, time_slot, admits, left_count, holding, timestamp)
                             VALUES (%s, %s, %s, %s, %s, %s)''',
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
        with get_connection() as conn:
            with conn.cursor() as c:
                c.execute("SELECT time_slot, admits, left_count, holding FROM entries WHERE date = %s ORDER BY time_slot", (selected_date,))
                rows = c.fetchall()

    return render_template('view.html', rows=rows, selected_date=selected_date)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8000)