"""`slidecold` command line: `slidecold <resource> <action> [ids] [--param value] [--data JSON|@file] [--file path]`.

Commands are generated from the operation table, so they always match the SDK.
"""

import argparse
import json
import os
import sys
from getpass import getpass
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import _config
from ._client import SlideCold
from ._exceptions import KEYS_URL, AuthenticationError, PermissionDeniedError, SlideColdError
from ._operations import OPERATIONS, RESOURCES, Operation
from ._version import __version__


def _kebab(name: str) -> str:
    return name.replace("_", "-")


def _common() -> argparse.ArgumentParser:
    # SUPPRESS so a flag given before the subcommand isn't reset by the subparser's default.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--api-key", default=argparse.SUPPRESS, help="API key (default: SLIDECOLD_API_KEY, then config)"
    )
    common.add_argument("--base-url", default=argparse.SUPPRESS, help="API base URL (default: production)")
    return common


def build_parser() -> argparse.ArgumentParser:
    common = _common()
    parser = argparse.ArgumentParser(
        prog="slidecold",
        parents=[common],
        description="SlideCold API from the command line. Output is JSON (CSV for exports).",
        epilog=f"Run `slidecold <command> --help` for details. Create an API key at {KEYS_URL}.\n"
        f"Config file: {_config.config_path()}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"slidecold {__version__}")
    sub = parser.add_subparsers(dest="resource", metavar="<command>")

    login = sub.add_parser("login", parents=[common], help="Save an API key to the config file")
    login.add_argument("--key", help="API key (prompted for if omitted)")
    sub.add_parser("logout", parents=[common], help="Remove the saved API key")

    groups: Dict[str, List[Operation]] = {}
    for op in OPERATIONS.values():
        groups.setdefault(op.resource, []).append(op)
    for resource, ops in groups.items():
        rp = sub.add_parser(resource, help=RESOURCES.get(resource), description=RESOURCES.get(resource))
        rsub = rp.add_subparsers(dest="action", metavar="<action>")
        for op in ops:
            _add_command(rsub, op, common)
        rp.set_defaults(resource_parser=rp)
    return parser


def _add_command(rsub: Any, op: Operation, common: argparse.ArgumentParser) -> None:
    description = f"{op.summary}.\n\n"
    if op.description:
        description += op.description + "\n\n"
    description += f"Scope: {op.scope}\nHTTP:  {op.method} {op.path}"
    ap = rsub.add_parser(
        _kebab(op.name),
        parents=[common],
        help=f"{op.summary} [{op.scope}]",
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    for p in op.path_params:
        ap.add_argument(p.py_name, metavar=p.py_name.upper(), help=p.description or None)
    for q in op.query_params:
        kwargs: Dict[str, Any] = {"dest": q.py_name, "required": q.required, "help": q.description or None}
        if q.schema.get("type") == "integer":
            kwargs["type"] = int
        if "enum" in q.schema:
            kwargs["choices"] = q.schema["enum"]
        ap.add_argument("--" + _kebab(q.py_name), **kwargs)
    if op.body in ("json", "json_or_multipart"):
        ap.add_argument("--data", help="JSON request body, or @path/to/body.json")
    if op.file_field:
        ap.add_argument(
            "--file", required=op.body == "multipart", help=f"Local file to upload as `{op.file_field}`"
        )
    ap.set_defaults(operation=op.id)


def _read_data(raw: Optional[str]) -> Any:
    if raw is None:
        return None
    text = Path(raw[1:]).read_text(encoding="utf-8") if raw.startswith("@") else raw
    try:
        return json.loads(text)
    except ValueError as e:
        raise SlideColdError(None, f"--data is not valid JSON: {e}") from e


def _print(result: Any) -> None:
    if result is None:
        return
    if isinstance(result, str):
        sys.stdout.write(result)
        if not result.endswith("\n"):
            sys.stdout.write("\n")
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))


def _login(args: argparse.Namespace) -> int:
    key = (args.key or getpass(f"SlideCold API key (create one at {KEYS_URL}): ")).strip()
    if not key:
        print("No API key given.", file=sys.stderr)
        return 1
    base_url = getattr(args, "base_url", None)
    with SlideCold(api_key=key, base_url=base_url, max_retries=0) as client:
        try:
            client.request("listCampaigns")
            note = ""
        except AuthenticationError as e:
            print(f"Error: invalid API key: {e}", file=sys.stderr)
            return 1
        except PermissionDeniedError:
            note = " (the key is valid but lacks campaigns:read; commands outside its scopes will return 403)"
    config = _config.load_config()
    config["apiKey"] = key
    if base_url:
        config["baseUrl"] = base_url
    path = _config.save_config(config)
    print(f"Logged in{note}. Key saved to {path}")
    if os.environ.get("SLIDECOLD_API_KEY"):
        print("Note: SLIDECOLD_API_KEY is set and takes precedence over the saved key.", file=sys.stderr)
    return 0


def _logout() -> int:
    config = _config.load_config()
    path = _config.config_path()
    if "apiKey" not in config:
        print("Not logged in.")
        return 0
    del config["apiKey"]
    if config:
        _config.save_config(config)
    else:
        path.unlink()
    print(f"Removed the API key from {path}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.resource is None:
            parser.print_help()
            return 0
        if args.resource == "login":
            return _login(args)
        if args.resource == "logout":
            return _logout()
        if getattr(args, "operation", None) is None:
            args.resource_parser.print_help()
            return 2
        op = OPERATIONS[args.operation]
        body = _read_data(getattr(args, "data", None))
        with SlideCold(
            api_key=getattr(args, "api_key", None), base_url=getattr(args, "base_url", None)
        ) as client:
            result = client.request(
                op.id,
                path={p.name: getattr(args, p.py_name) for p in op.path_params},
                query={q.name: getattr(args, q.py_name) for q in op.query_params},
                body=body,
                file=getattr(args, "file", None),
            )
        _print(result)
        return 0
    except SlideColdError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
