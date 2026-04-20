import argparse

from migration_runner import apply_pending, status


def _print_status() -> None:
    migration_status = status()
    print(f"Total migrations: {migration_status['total']}")
    print(f"Applied: {len(migration_status['applied'])}")
    print(f"Pending: {len(migration_status['pending'])}")

    if migration_status["pending"]:
        print("\nPending migrations:")
        for item in migration_status["pending"]:
            print(f"- {item['version']}  {item['filename']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="SQLite migration runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Show migration status")

    up_parser = subparsers.add_parser("up", help="Apply pending migrations")
    up_parser.add_argument("--target", help="Apply up to this version (e.g., 0001)")

    args = parser.parse_args()

    if args.command == "status":
        _print_status()
        return

    if args.command == "up":
        applied_now = apply_pending(target=args.target)
        if applied_now:
            print("Applied migrations:")
            for migration_name in applied_now:
                print(f"- {migration_name}")
        else:
            print("No pending migrations to apply.")
        return


if __name__ == "__main__":
    main()
