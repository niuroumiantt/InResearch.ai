# Task authority convergence

## Evidence

PR #188's independent review and the current `4ad9f2f` source agree on one observable split: `workflow.workorders.build()` appends `question_tasks()` to `reports/workorders.json`, while `knowledge.registry.current_tasks()` computes the same question tasks again and filters only the projection's question rows. `web/pages/index.html` reads the projection directly; `team.html`, assignment, and `/api/research` use `current_tasks()`. Counts can therefore differ after a question or adoption change.

## Authority and target duties

`framework/03_bom_and_collaboration.md` requires research views, team, and assignment to share `registry.current_tasks()`. `framework/09_software_contracts.md` requires interfaces to adapt parameters and output rather than recompute domain state.

- `registry.current_tasks()` owns the merged current task set and question tasks.
- `registry.task_board()` owns the task API projection.
- `workorders.build()` owns module-gap orders and their statistics only.
- `/api/tasks`, homepage, team, and assignment consume the registry task board.

## Consumers and migration result

| Consumer | Previous input | Result |
|---|---|---|
| `index.html` | static workorders JSON | `/api/tasks` |
| `team.html` | `/api/tasks` | retained |
| `interfaces/http.py` | registry tasks plus file statistics | `registry.task_board()` |
| `workflow/commands.py`, `workflow/submissions.py` | `registry.current_tasks()` | retained |
| `workorders.py` | writes question and module tasks | module tasks only |

## File migration and deletion

`file-plan.csv` inventories every baseline file. Delete the final `question_tasks()` append loop in `workorders.build()` and homepage direct workorders fetch. The JSON projection remains solely for module-gap workorders and module statistics.
