"""One-shot Saudi/UAE OpenSky collector.

For the continuous Kafka/MongoDB pipeline use ``gulf_live.py``.  This command
exists for local inspection and exports the same normalized aircraft records.
"""

import argparse
import csv
from pathlib import Path

from gulf_live import OpenSkyGulfClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect current Saudi/UAE Gulf aircraft observations")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--output", default="collected_data/gulf_live_flights.csv")
    args = parser.parse_args()

    records = OpenSkyGulfClient().fetch()[: args.limit]
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(records[0]) if records else ["icao24", "callsign", "snapshot_at"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    print(f"Saved {len(records)} Saudi/UAE Gulf aircraft observations to {path}")


if __name__ == "__main__":
    main()
