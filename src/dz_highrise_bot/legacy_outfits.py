from __future__ import annotations

import json
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=4)
def load_legacy_outfits(module_path: Path) -> dict[str, list[dict[str, Any]]]:
    script = (
        "const path = process.argv[1];"
        "const data = require(path);"
        "process.stdout.write(JSON.stringify(data));"
    )
    result = subprocess.run(
        ["node", "-e", script, str(module_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    return {
        "casual": data.get("casualoutfit", []),
        "formal": data.get("formaloutfit", []),
        "party": data.get("partyoutfit", []),
    }


def select_outfit(module_path: Path, name: str) -> list[dict[str, Any]]:
    outfits = load_legacy_outfits(module_path)
    return outfits.get(name, outfits.get("formal", []))
