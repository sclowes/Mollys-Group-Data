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

def get_current_time_slot():
    now = datetime.now()
    minute = 30 if now.minute >= 30 else 0
    return f"{now.hour:02}:{minute:02}"

def calculate_holding_for(date_str):
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT SUM(admits), SUM(left_count) FROM entries WHERE date = %s", (date_str,))
            result = c.fetchone()
            total_admits = result[0] or 0
            total_left = result[1] or 0
            return total_admits - total_left, total_admits, total_left

@app.route('/')
def index():
    return redirect(url_for('submit_entry'))

@app.route('/submit', methods=['GET', 'POST'])
def submit_entry():
    times = [f"{h:02}:{m:02}" for h in range(15, 24) for m in (0, 30)] + [f"{h:02}:{m:02}" for h in range(0, 7) for m in (0, 30)]
    now = datetime.now()
    default_time = get_current_time_slot()
    night_start_date = get_night_start(now).isoformat()
    holding, total_admits, total_left = calculate_holding_for(night_start_date)

    if request.method == 'POST':
        admits = int(request.form['admits'])
        left_count = int(request.form['left_count'])
        time_slot = request.form['time_slot']

        new_holding = holding + admits - left_count

        with get_connection() as conn:
            with conn.cursor() as c:
                c.execute("SELECT id, admits, left_count FROM entries WHERE date = %s AND time_slot = %s", (night_start_date, time_slot))
                existing = c.fetchone()

                if existing:
                    current_id, current_admits, current_left = existing
                    return render_template('confirm.html',
                                           time_slot=time_slot,
                                           existing={'admits': current_admits, 'left': current_left},
                                           new={'admits': admits, 'left': left_count},
                                           date=night_start_date,
                                           holding=new_holding,
                                           entry_id=current_id)

                c.execute('''INSERT INTO entries (date, time_slot, admits, left_count, holding, timestamp)
                             VALUES (%s, %s, %s, %s, %s, %s)''',
                          (night_start_date, time_slot, admits, left_count, new_holding, now.isoformat()))
                conn.commit()

        return redirect(url_for('submit_entry'))

    return render_template('submit.html', times=times, default_time=default_time,
                           holding=holding, total_admits=total_admits, total_left=total_left)

@app.route('/confirm', methods=['POST'])
def confirm_entry():
    selection = request.form['choice']
    entry_id = int(request.form['entry_id'])
    time_slot = request.form['time_slot']
    night_start_date = request.form['date']
    now = datetime.now()

    if selection == 'new':
        admits = int(request.form['new_admits'])
        left_count = int(request.form['new_left'])
    else:
        admits = int(request.form['existing_admits'])
        left_count = int(request.form['existing_left'])

    holding = calculate_holding_for(night_start_date)[0] + admits - left_count

    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute('''UPDATE entries SET admits = %s, left_count = %s, holding = %s, timestamp = %s WHERE id = %s''',
                      (admits, left_count, holding, now.isoformat(), entry_id))
            conn.commit()

    return redirect(url_for('submit_entry'))

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