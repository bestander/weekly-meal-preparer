import argparse
import asyncio
import sys

from purchasing.main import run_pipeline, DEFAULT_RECIPE_PATH, DEFAULT_DB_PATH, DEFAULT_SESSION_PATH


def main():
    parser = argparse.ArgumentParser(prog="purchasing", description="Meal Rotation — ingredient ordering")
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Run the weekly ordering pipeline")
    run_p.add_argument("--recipe", default=DEFAULT_RECIPE_PATH)
    run_p.add_argument("--db", default=DEFAULT_DB_PATH)
    run_p.add_argument("--session", default=DEFAULT_SESSION_PATH)
    run_p.add_argument(
        "--checkout",
        action="store_true",
        help="Automatically proceed to checkout and place the order (default: stop at cart)",
    )

    auth_p = sub.add_parser("auth", help="Authentication commands")
    auth_sub = auth_p.add_subparsers(dest="auth_command")
    auth_sub.add_parser("login", help="Open browser to log in and save session")

    args = parser.parse_args()

    if args.command == "run":
        run_pipeline(args.recipe, args.db, args.session, checkout=args.checkout)
    elif args.command == "auth" and args.auth_command == "login":
        from purchasing.auth import login_interactive
        asyncio.run(login_interactive(DEFAULT_SESSION_PATH))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
