"""
seed_admin.py — One-time script to create the platform admin user.

Run from the backend/ directory:
    python seed_admin.py

Reads DB credentials from .env (same as the main app).
The platform_admin role has full access: can register new users
(hospital_admin, doctor), manage facilities, and view all data.
"""

import os
import sys
import bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# ── Admin credentials ────────────────────────────────────────────────────────
ADMIN_EMAIL     = "user@example.com"
ADMIN_PASSWORD  = "password"          # change after first login
ADMIN_FULL_NAME = "Full Name"
ADMIN_ROLE      = "platform_admin"     # top-level role: can register hospital_admin / doctor
# ─────────────────────────────────────────────────────────────────────────────


def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "pre_consultation_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        cursor_factory=RealDictCursor,
    )


def seed_admin():
    password_hash = bcrypt.hashpw(ADMIN_PASSWORD.encode(), bcrypt.gensalt(rounds=12)).decode()

    with get_connection() as conn:
        with conn.cursor() as cur:

            # Guard: skip if an admin already exists
            cur.execute(
                "SELECT user_id, email FROM users WHERE role = 'platform_admin' LIMIT 1"
            )
            existing = cur.fetchone()
            if existing:
                print(
                    f"[skip] platform_admin already exists "
                    f"(user_id={existing['user_id']}, email={existing['email']})"
                )
                return

            cur.execute(
                """
                INSERT INTO users (email, password_hash, full_name, role)
                VALUES (%s, %s, %s, %s)
                RETURNING user_id, email, full_name, role, created_at
                """,
                (ADMIN_EMAIL, password_hash, ADMIN_FULL_NAME, ADMIN_ROLE),
            )
            user = cur.fetchone()
            conn.commit()

    print("[ok] Platform admin created:")
    print(f"     user_id   : {user['user_id']}")
    print(f"     email     : {user['email']}")
    print(f"     full_name : {user['full_name']}")
    print(f"     role      : {user['role']}")
    print(f"     created_at: {user['created_at']}")
    print()
    print("[!] Remember to change the password after your first login.")


if __name__ == "__main__":
    try:
        seed_admin()
    except psycopg2.OperationalError as e:
        print(f"[error] Could not connect to the database:\n  {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)
