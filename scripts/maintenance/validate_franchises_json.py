from pathlib import Path
import json


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    dirp = root / "vocab" / "franchises"
    bad = []
    for fp in sorted(dirp.glob("*.json")):
        try:
            json.loads(fp.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"ERROR: {fp.relative_to(root)} -> {e}")
            bad.append(fp)
    if not bad:
        print("All franchise JSON files parsed successfully.")
        return 0
    else:
        print(f"{len(bad)} file(s) had JSON parse errors.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
