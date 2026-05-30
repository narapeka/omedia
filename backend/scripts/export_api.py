from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import create_app


def main() -> int:
    args = list(sys.argv[1:])
    surface = "target"
    if "--surface" in args:
        index = args.index("--surface")
        try:
            surface = args[index + 1]
        except IndexError as exc:
            raise SystemExit("--surface requires target") from exc
        del args[index:index + 2]
    if surface != "target":
        raise SystemExit("Only --surface target is available after Phase 8 cleanup")
    output = Path(args[0]) if args else Path("../frontend/src/api/openapi.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    app = create_app(openapi_surface=surface)
    output.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8")
    app.state.runtime_manager.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
