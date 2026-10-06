"""Показать все кластеры из 03_clusters.json в читаемом виде."""

import json
import sys
from pathlib import Path

run_id = sys.argv[1] if len(sys.argv) > 1 else None
if not run_id:
    print("Usage: python show_clusters.py <run_id>")
    sys.exit(1)

path = Path("runs") / run_id / "03_clusters.json"
if not path.exists():
    print(f"Not found: {path}")
    sys.exit(1)

d = json.loads(path.read_text(encoding="utf-8"))
clusters = d["clusters"]
print(f"Total clusters: {d['total_clusters']}")
print()
print(f"{'canonical':<40} {'freq':>5}  aliases")
print("-" * 100)
for c in clusters:
    aliases = ", ".join(c["aliases"][:6])
    if len(c["aliases"]) > 6:
        aliases += f"  (+{len(c['aliases']) - 6} more)"
    print(f"{c['canonical']:<40} {c['total_frequency']:>5}  {aliases}")
