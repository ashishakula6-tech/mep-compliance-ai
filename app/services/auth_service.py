from __future__ import annotations
import sqlite3
import hashlib
import secrets
from datetime import datetime
from typing import Optional

DB_PATH = "mep_compliance.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT DEFAULT '',
            role TEXT DEFAULT 'engineer',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS project_reports (
            project_id TEXT NOT NULL,
            report_id TEXT NOT NULL,
            added_at TEXT NOT NULL,
            PRIMARY KEY (project_id, report_id)
        );
    """)
    conn.commit()
    conn.close()


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def create_user(username: str, email: str, password: str, full_name: str = "") -> dict:
    conn = get_db()
    try:
        uid = secrets.token_hex(8)
        conn.execute(
            "INSERT INTO users (id, username, email, password_hash, full_name, created_at) VALUES (?,?,?,?,?,?)",
            (uid, username.strip(), email.strip().lower(), _hash(password), full_name, datetime.now().isoformat()),
        )
        conn.commit()
        return {"id": uid, "username": username, "email": email, "full_name": full_name, "role": "engineer"}
    except sqlite3.IntegrityError:
        raise ValueError("Username or email already registered")
    finally:
        conn.close()


def login(username_or_email: str, password: str) -> dict:
    conn = get_db()
    try:
        user = conn.execute(
            "SELECT * FROM users WHERE (username=? OR email=?) AND password_hash=?",
            (username_or_email, username_or_email.lower(), _hash(password)),
        ).fetchone()
        if not user:
            raise ValueError("Invalid credentials")
        token = secrets.token_hex(32)
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at) VALUES (?,?,?)",
            (token, user["id"], datetime.now().isoformat()),
        )
        conn.commit()
        return {"token": token, "user": dict(user)}
    finally:
        conn.close()


def get_user_by_token(token: str) -> Optional[dict]:
    if not token:
        return None
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT u.id, u.username, u.email, u.full_name, u.role, u.created_at "
            "FROM users u JOIN sessions s ON u.id=s.user_id WHERE s.token=?",
            (token,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def logout(token: str):
    conn = get_db()
    conn.execute("DELETE FROM sessions WHERE token=?", (token,))
    conn.commit()
    conn.close()


def create_project(name: str, description: str, user_id: str) -> dict:
    conn = get_db()
    try:
        pid = secrets.token_hex(8)
        conn.execute(
            "INSERT INTO projects (id, name, description, user_id, created_at) VALUES (?,?,?,?,?)",
            (pid, name.strip(), description, user_id, datetime.now().isoformat()),
        )
        conn.commit()
        return {"id": pid, "name": name, "description": description, "user_id": user_id, "created_at": datetime.now().isoformat()}
    finally:
        conn.close()


def get_projects(user_id: str) -> list:
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM projects WHERE user_id=? ORDER BY created_at DESC", (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def add_report_to_project(project_id: str, report_id: str):
    conn = get_db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO project_reports VALUES (?,?,?)",
            (project_id, report_id, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def get_project_report_ids(project_id: str) -> list:
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT report_id FROM project_reports WHERE project_id=? ORDER BY added_at DESC",
            (project_id,),
        ).fetchall()
        return [r["report_id"] for r in rows]
    finally:
        conn.close()
