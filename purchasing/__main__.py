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

    web_p = sub.add_parser("web", help="Web UI commands (JSON line protocol)")
    web_sub = web_p.add_subparsers(dest="web_command")
    web_resolve = web_sub.add_parser("resolve", help="Resolve ingredients with progress events")
    web_resolve.add_argument("--recipe", default=DEFAULT_RECIPE_PATH)
    web_resolve.add_argument("--db", default=DEFAULT_DB_PATH)
    web_resolve.add_argument("--session", default=DEFAULT_SESSION_PATH)
    web_finish = web_sub.add_parser("finish", help="Apply approval and build cart")
    web_finish.add_argument("--approval", required=True, help="Path to approval JSON file")
    web_finish.add_argument("--db", default=DEFAULT_DB_PATH)
    web_finish.add_argument("--session", default=DEFAULT_SESSION_PATH)
    web_finish.add_argument("--checkout", action="store_true")
    web_search = web_sub.add_parser("search", help="Search one ingredient")
    web_search.add_argument("ingredient")
    web_search.add_argument("--session", default=DEFAULT_SESSION_PATH)

    args = parser.parse_args()

    if args.command == "run":
        run_pipeline(args.recipe, args.db, args.session, checkout=args.checkout)
    elif args.command == "auth" and args.auth_command == "login":
        from purchasing.auth import login_interactive
        asyncio.run(login_interactive(DEFAULT_SESSION_PATH))
    elif args.command == "web":
        from purchasing.web import cmd_finish, cmd_resolve, cmd_search_one
        if args.web_command == "resolve":
            sys.exit(cmd_resolve(args.recipe, args.db, args.session))
        if args.web_command == "finish":
            sys.exit(cmd_finish(args.approval, args.db, args.session, args.checkout))
        if args.web_command == "search":
            sys.exit(cmd_search_one(args.ingredient, args.session))
        web_p.print_help()
        sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
