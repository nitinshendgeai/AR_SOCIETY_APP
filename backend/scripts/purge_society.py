"""
Platform-admin maintenance script: permanently delete all data of ONE society.

    python scripts/purge_society.py <SOCIETY_CODE>                 # preview, then ask to re-type the code
    python scripts/purge_society.py <SOCIETY_CODE> --dry-run       # preview only, nothing is deleted
    python scripts/purge_society.py <SOCIETY_CODE> --yes           # no prompt (automation)
    python scripts/purge_society.py <SOCIETY_CODE> --delete-society  # also remove the society record itself
    python scripts/purge_society.py <SOCIETY_CODE> --wipe-logins   # also delete the default logins (kept by default)

Run it from the backend/ directory against the database in DATABASE_URL (the same env var the app uses).

What is deleted: every row that belongs to the society — all tables carrying a `society_id`, plus the child tables
reached from them through foreign keys (flats, residents, bill lines, voucher entries, poll options, ...), plus the
society's users and their sessions / device tokens / notifications / audit-log rows.

What is kept: the society's default logins (admin / chairman / secretary / treasurer @<code>.com), other societies, platform-admin (superadmin) accounts, and the global roles / permissions / forms.
By default the `societies` row is kept (so the code stays reserved and can be re-onboarded); pass --delete-society
to remove it too.

Everything runs in a single transaction: any error rolls the whole purge back. Uploaded files on disk or in object
storage are NOT touched.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.society_purge import find_society, purge_society  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Permanently delete all data of one society (platform admin only).")
    ap.add_argument("society_code", help="society_code of the society to clean")
    ap.add_argument("--dry-run", action="store_true", help="show what would be deleted, delete nothing")
    ap.add_argument("--delete-society", action="store_true", help="also delete the society record itself")
    ap.add_argument("--wipe-logins", action="store_true", help="also delete the default logins (admin, chairman, secretary, treasurer)")
    ap.add_argument("--yes", action="store_true", help="skip the interactive confirmation")
    args = ap.parse_args(argv)

    from app.db.session import get_session_factory
    db = get_session_factory()()
    try:
        found = find_society(db, args.society_code)
        if found is None:
            raise LookupError(f"No society with code {args.society_code!r}.")
        society_id, society_name = found
        preview = purge_society(db, society_id, dry_run=True, delete_society=args.delete_society,
                                 keep_default_logins=not args.wipe_logins)
        db.rollback()
        print(f"Society : {society_name}  (code {args.society_code.upper()}, id {society_id})")
        total = sum(preview["counts"].values())
        for table, n in sorted(preview["counts"].items()):
            print(f"  {table:<40}{n:>8}")
        print(f"  {'TOTAL':<40}{total:>8}")
        if args.dry_run:
            print("Dry run — nothing deleted.")
            return 0

        if not args.yes:
            typed = input(f"\nThis permanently deletes the data above. Re-type the society code ({args.society_code.upper()}) to confirm: ")
            if typed.strip().upper() != args.society_code.strip().upper():
                print("Code did not match — aborted, nothing deleted.")
                return 1

        result = purge_society(db, society_id, delete_society=args.delete_society, keep_default_logins=not args.wipe_logins)
        db.commit()
        print(f"Done — {sum(result['counts'].values())} rows deleted.")
        return 0
    except (LookupError, RuntimeError) as e:
        db.rollback()
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
