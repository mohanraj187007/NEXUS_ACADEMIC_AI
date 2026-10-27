"""
Administrative User Provisioning CLI Utility
Academic Attendance Pattern & Risk Analytics System (NEXUS ACADEMIC AI)

Enables operators and DevOps engineers to securely provision an initial Administrator
or additional privileged institutional accounts without exposing passwords in command histories.
Uses FIPS/NIST PBKDF2-HMAC-SHA256 password hashing with a cryptographic salt.

Usage:
    Interactive Prompt:
        python create_admin.py

    Non-Interactive / Scripted (CI/CD / Orchestration):
        python create_admin.py --username admin_ops --email ops@vsbec.com --fullname "Director of Operations" --password "SecureAdmin@2026!"
"""

import sys
import os
import argparse
import getpass

# Add project path to sys.path
PROJECT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "project1")
if os.path.exists(PROJECT_DIR) and PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

try:
    from database.database import init_db, create_new_user, get_user_by_credentials
    from utils.security import validate_password_strength
except ImportError:
    # If running directly from within project1 directory
    from project1.database.database import init_db, create_new_user, get_user_by_credentials
    from project1.utils.security import validate_password_strength


def main():
    parser = argparse.ArgumentParser(
        description="NEXUS ACADEMIC AI - Provision Authorized Administrator Account"
    )
    parser.add_argument("--username", help="Unique institutional username")
    parser.add_argument("--email", help="Institutional email address")
    parser.add_argument("--fullname", help="Full legal/institutional name")
    parser.add_argument("--institution_id", default="INST_001", help="Tenant institution ID (default: INST_001)")
    parser.add_argument("--password", help="Account password (omit for secure masked prompt)")
    parser.add_argument("--role", default="Administrator", choices=["Administrator", "Academic Coordinator", "Faculty", "Student"], help="Account role")

    args = parser.parse_args()

    # Ensure utf-8 encoding on Windows console
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    # Initialize database if needed
    init_db()

    print("=" * 70)
    print("[NEXUS ACADEMIC AI] Privileged User Provisioning CLI")
    print("=" * 70)

    # 1. Collect Username
    username = args.username
    if not username:
        username = input("Enter Institutional Username: ").strip().lower()
    else:
        username = username.strip().lower()

    if not username:
        print("[-] Error: Username cannot be blank.")
        sys.exit(1)

    existing = get_user_by_credentials(username)
    if existing:
        print(f"[-] Error: An account with username or email '{username}' already exists.")
        sys.exit(1)

    # 2. Collect Full Name
    fullname = args.fullname
    if not fullname:
        fullname = input("Enter Full Name: ").strip()
    if not fullname:
        fullname = "System Administrator"

    # 3. Collect Email
    email = args.email
    if not email:
        email = input("Enter Institutional Email Address: ").strip().lower()

    # 4. Collect Password
    password = args.password
    if not password:
        while True:
            p1 = getpass.getpass("Enter Secure Password: ")
            p2 = getpass.getpass("Confirm Password: ")
            if p1 != p2:
                print("[-] Passwords do not match. Please try again.\n")
                continue
            is_valid, reason = validate_password_strength(p1)
            if not is_valid:
                print(f"[-] Password policy violation: {reason}\n")
                continue
            password = p1
            break
    else:
        is_valid, reason = validate_password_strength(password)
        if not is_valid:
            print(f"[-] Password policy violation: {reason}")
            sys.exit(1)

    # 5. Create User Record
    ok, message, user_id = create_new_user({
        "username": username,
        "full_name": fullname,
        "email": email or None,
        "role": args.role,
        "institution_id": args.institution_id,
        "password": password,
        "must_change_password": False
    })

    if ok:
        print("-" * 70)
        print(f"[+] Success: {message}")
        print(f"   User ID:         {user_id}")
        print(f"   Username:        {username}")
        print(f"   Full Name:       {fullname}")
        print(f"   Role:            {args.role}")
        print(f"   Institution:     {args.institution_id}")
        print(f"   Security Hash:   PBKDF2-HMAC-SHA256 (600,000 iterations)")
        print("-" * 70)
    else:
        print(f"[-] Provisioning Failed: {message}")
        sys.exit(1)


if __name__ == "__main__":
    main()
