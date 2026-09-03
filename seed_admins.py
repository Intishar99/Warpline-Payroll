"""
Creates an admin login account. Run this directly -- not a web route, no signup page
exists on purpose. Run once per admin account needed.

Usage: python seed_admins.py

The password is typed interactively (hidden) and only the HASH gets written to the
database. The plaintext never touches this file, never gets logged, never gets committed.
"""

import getpass
from app import app, db
from models import AdminUser
from werkzeug.security import generate_password_hash


def main():
    with app.app_context():
        username = input("New admin username: ").strip()

        if AdminUser.query.filter_by(username=username).first():
            print(f"A user named '{username}' already exists. Aborting.")
            return

        password = getpass.getpass("New admin password (hidden as you type): ")
        confirm = getpass.getpass("Confirm password: ")

        if password != confirm:
            print("Passwords didn't match. Aborting -- run the script again.")
            return
        if len(password) < 8:
            print("Password should be at least 8 characters. Aborting.")
            return

        user = AdminUser(username=username, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        print(f"Admin account '{username}' created successfully.")


if __name__ == "__main__":
    main()
