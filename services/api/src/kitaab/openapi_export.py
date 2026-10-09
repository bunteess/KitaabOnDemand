"""Write the OpenAPI contract to a file, or check that the file is current.

python -m kitaab.openapi_export packages/contracts/openapi.json
python -m kitaab.openapi_export --check packages/contracts/openapi.json
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from kitaab.main import create_app


def render() -> str:
    spec = create_app().openapi()
    return json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--check", action="store_true", help="fail if the file is stale")
    args = parser.parse_args(argv)
    rendered = render()
    if args.check:
        current = args.path.read_text(encoding="utf-8") if args.path.exists() else ""
        if current != rendered:
            print(f"{args.path} is stale: run 'make contracts'", file=sys.stderr)  # noqa: T201
            return 1
        return 0
    args.path.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
