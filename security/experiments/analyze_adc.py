"""Summarize EXQ-10 raw ADC capture without hiding errors or changing tolerance."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path


def summarize(rows):
    if not rows or [int(r["sample"]) for r in rows] != list(range(len(rows))):
        raise ValueError("missing/duplicate ADC samples")
    values = [int(r["raw"]) for r in rows if r["status"] == "OK"]
    return {"attempts": len(rows), "valid": len(values), "errors": len(rows)-len(values),
            "status_counts": dict(Counter(r["status"] for r in rows)),
            "min_raw": min(values) if values else None, "max_raw": max(values) if values else None,
            "outside_current_tolerance": sum(v < -32 or v > 26432 for v in values),
            "histogram": dict(sorted(Counter(values).items())),
            "complete_1000": len(rows) >= 1000 and len(values) == len(rows),
            "decision": "measurement only; no automatic tolerance change"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path")
    parser.add_argument("--position", choices=["low", "middle", "high"], required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        with Path(args.csv_path).open(encoding="utf-8", newline="") as stream:
            result = summarize(list(csv.DictReader(stream)))
        result["position"] = args.position
        with Path(args.out).open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
        print({k: v for k, v in result.items() if k != "histogram"})
        return 0 if result["complete_1000"] else 1
    except (OSError, ValueError, KeyError) as error:
        print(error)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
