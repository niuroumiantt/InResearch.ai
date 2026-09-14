"""Create complete task-authority file plan before edits."""
import csv, json, subprocess
from pathlib import Path
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
scope = json.loads((OUT / 'scope.json').read_text())
paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', scope['baseline']], cwd=ROOT, text=True).splitlines()
changed = set(scope['changed'])
with (OUT / 'file-plan.csv').open('w', newline='') as stream:
    writer = csv.writer(stream, lineterminator='\n'); writer.writerow(('path', 'action', 'reason'))
    for path in paths:
        writer.writerow((path, 'modify' if path in changed else 'retain', 'declared task authority migration' if path in changed else 'outside this batch; preserve bytes and authority'))
    for path in sorted(changed - set(paths)): writer.writerow((path, 'add', 'declared task authority migration'))
print(json.dumps({'baseline_files': len(paths), 'declared_paths': len(changed)}))
