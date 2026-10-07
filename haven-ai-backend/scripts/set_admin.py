"""
Grants (or removes) administrator access for a Haven AI account.

Admin access is the Firebase custom claim `admin: true` on the user's
sign-in account. Only someone holding the service-account key
(firebase-credentials.json) can set it, so it cannot be faked from a browser.
The user must sign out and in again (or wait up to an hour) to receive a
token carrying the new claim.

    python scripts/set_admin.py someone@example.com          # grant
    python scripts/set_admin.py someone@example.com --revoke # remove
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from firebase_admin import auth  # noqa: E402

from app.core.firebase import get_app  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("email")
    parser.add_argument("--revoke", action="store_true", help="remove admin access instead")
    args = parser.parse_args()

    app = get_app()
    try:
        user = auth.get_user_by_email(args.email, app=app)
    except auth.UserNotFoundError:
        print(f"No account with email {args.email}. Sign up on the website first.")
        return 1

    claims = dict(user.custom_claims or {})
    if args.revoke:
        claims.pop("admin", None)
    else:
        claims["admin"] = True
    auth.set_custom_user_claims(user.uid, claims or None, app=app)
    print(f"{'Removed' if args.revoke else 'Granted'} admin access for {args.email} (uid {user.uid}).")
    print("Sign out and sign in again on the website to apply it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
