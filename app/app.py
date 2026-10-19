import os
import time
import psycopg2
from flask import Flask, jsonify, request

app = Flask(__name__)


def get_conn():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "db"),
        dbname=os.getenv("DB_NAME", "tasks"),
        user=os.getenv("DB_USER", "app"),
        password=os.getenv("DB_PASSWORD", "secret"),
    )


def init_db():
    # DB may still be starting, so retry a few times
    for _ in range(10):
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute(
                "CREATE TABLE IF NOT EXISTS tasks "
                "(id SERIAL PRIMARY KEY, title TEXT NOT NULL);"
            )
            conn.commit()
            cur.close()
            conn.close()
            return
        except psycopg2.OperationalError:
            time.sleep(2)
    raise RuntimeError("Database is not reachable")


@app.route("/health")
def health():
    return jsonify(status="ok")


@app.route("/tasks", methods=["GET"])
def list_tasks():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, title FROM tasks ORDER BY id;")
    rows = [{"id": r[0], "title": r[1]} for r in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(rows)


@app.route("/tasks", methods=["POST"])
def add_task():
    title = (request.get_json(silent=True) or {}).get("title")
    if not title:
        return jsonify(error="title is required"), 400
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO tasks (title) VALUES (%s) RETURNING id;", (title,))
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return jsonify(id=new_id, title=title), 201


init_db()
