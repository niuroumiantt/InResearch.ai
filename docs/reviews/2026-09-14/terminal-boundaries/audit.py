"""Create a complete baseline file plan before changing terminal boundaries."""
import csv
import json
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
SCOPE = json.loads((OUT / "scope.json").read_text())

paths = subprocess.check_output(
    ["git", "ls-tree", "-r", "--name-only", SCOPE["baseline"]], cwd=ROOT, text=True
).splitlines()
changed = set(SCOPE["changed"])
with (OUT / "file-plan.csv").open("w", newline="") as stream:
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("path", "action", "reason"))
    for path in paths:
        action = "modify" if path in changed else "retain"
        reason = "declared boundary migration" if path in changed else "outside this batch; preserve bytes and authority"
        writer.writerow((path, action, reason))
    for path in sorted(changed - set(paths)):
        writer.writerow((path, "add", "declared boundary migration"))
print(json.dumps({"baseline_files": len(paths), "declared_paths": len(changed)}))
