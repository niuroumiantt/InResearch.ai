# Terminal batch and Office ownership review

## Current evidence

Baseline `342e009f4a8441a3d04377103abde6ee0fd9fdc8` has 780 tracked files.

`src/inresearch/workflow/terminal_batch.py` is 623 lines and combines candidate
selection, batch file generation, verdict persistence, activity-rate reporting,
and duplicate-version discovery.  Its running consumers are `workflow.score`,
`workflow.attribution`, and `workflow.progress`; its command entry is
`interfaces.cli`.  The direct test consumer set is
`test_model_runtime`, `test_m4_triage_extract`, `test_m4_triage_local`,
`test_m4_triage_versions`, and `test_m4_redo_reads`.

`materials.triage`, `workflow.terminal_batch`, and `delivery.reading_packet`
import `adapters.office`.  `adapters.office` and its four private helper modules
only parse local material bytes; they neither call an external service nor
adapt an external protocol.  Their location reverses the stated dependency
direction: the materials domain depends on an adapter that is actually domain
parsing logic.

## Target responsibilities and authority

`framework/09_software_contracts.md` is the authority for use-case and write
boundaries; `framework/04_reading_scoring_standard.md` is the authority for
one current reading result and revision conflict handling.

- `materials.office_text`: parse Office containers into bounded text and
  extraction metadata.  It owns no queue, model, verdict, or write policy.
- `workflow.batch_selection`: select/retry material candidates and normalize
  preview text.  It performs no writes.
- `workflow.batch_recording`: parse terminal verdict input and commit a result
  with its expected revision.  The records ledger remains the sole writer.
- `workflow.batch_reporting`: calculate activity rate and report duplicate
  candidate groups.  It performs no writes.
- `workflow.terminal_batch`: command composition only.

## Public consumers and required migration result

| Current implementation | Consumer | Result |
|---|---|---|
| `adapters.office*` | `materials.triage` | migrate to `materials.office_text` |
| `adapters.office*` | `workflow.terminal_batch` | migrate to `materials.office_text` |
| `adapters.office*` | `delivery.reading_packet` | migrate to `materials.office_text` |
| `adapters.office*` | Office extraction tests | migrate imports; preserve container/malformed-file cases |
| `terminal_batch` selection API | `workflow.score`, `workflow.attribution` | migrate to `batch_selection` |
| `terminal_batch` activity rate | `workflow.progress` | migrate to `batch_reporting` |
| `terminal_batch` CLI | `interfaces.cli` | retain command module as composition entry |
| `terminal_batch` tests | five listed test modules | migrate direct helpers to owners; retain CLI integration tests |

## Full file migration and removal list

`file-plan.csv` inventories every baseline path.  The implementation may alter
only the declared files in `scope.json`, except dated audit evidence and
generated governance manifests.  Old implementation deletion target:

- `src/inresearch/adapters/office.py`
- `src/inresearch/adapters/office_biff.py`
- `src/inresearch/adapters/office_container.py`
- `src/inresearch/adapters/office_grid.py`
- `src/inresearch/adapters/office_ooxml.py`
- `src/inresearch/adapters/office_ppt.py`

No compatibility re-export is allowed after every listed consumer migrates.
The command filename `workflow/terminal_batch.py` remains because it is the
registered CLI command, but it must not retain business implementations.

## Required verification

Run Office format and malformed-container tests; terminal pack/record tests;
revision conflict, partial verdict, retry cohort, deterministic concurrent
extraction, and same-report version replacement tests.  Then run strict data,
registry, governance, and the complete test suite.  A passing suite verifies
the declared cases only; scene/UI and later directory work remain separate.
