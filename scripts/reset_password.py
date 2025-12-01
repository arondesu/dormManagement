#!/usr/bin/env python3
"""
Reset user passwords in the `manager` database.
Usage:
  python scripts/reset_password.py --username admin1 --password "NewPass123"
  python scripts/reset_password.py --all --password "CommonPass123"

This script uses the same `db.get_db_connection()` function as your app and
Werkzeug's password hasher to store proper hashed passwords so login works.
"""
import argparse
from werkzeug.security import generate_password_hash
import sys

# adjust import path to import db from project
import os
import pathlib
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from db import get_db_connection


def update_password(username, password):
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to DB")
        return False
    cursor = conn.cursor()
    try:
        hashed = generate_password_hash(password)
        cursor.execute("UPDATE users SET password_hash=%s WHERE username=%s", (hashed, username))
        conn.commit()
        print(f"Updated password for {username}")
        return True
    except Exception as e:
        print("Error:", e)
        return False
    finally:
        cursor.close()
        conn.close()


def update_all(password):
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to DB")
        return False
    cursor = conn.cursor()
    try:
        hashed = generate_password_hash(password)
        cursor.execute("UPDATE users SET password_hash=%s", (hashed,))
        conn.commit()
        print("Updated password for all users")
        return True
    except Exception as e:
        print("Error:", e)
        return False
    finally:
        cursor.close()
        conn.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--username', help='Username to update')
    p.add_argument('--password', help='New plaintext password', required=True)
    p.add_argument('--all', action='store_true', help='Update all users to the same password')
    args = p.parse_args()

    if args.all:
        confirm = input(f"Are you sure you want to set the same password for ALL users? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Aborted")
            return
        update_all(args.password)
    elif args.username:
        update_password(args.username, args.password)
    else:
        print("Either --username or --all must be provided")

if __name__ == '__main__':
    main()
