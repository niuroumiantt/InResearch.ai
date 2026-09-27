# NVIDIA M5 → AWS validation delivery

## Accepted scope

This validation uses M5-local Fetchspec originals and M5 Claude Code CLI reading, with candidate content and a separate pilot-status projection sent directly to the AWS-hosted inresearch.ai receiver. Spark is explicitly excluded: no NVIDIA package, status, or task is sent to Spark, and existing Spark L1/L2 work remains untouched. Spark permanent original storage is deferred until this validation succeeds.

The public progress endpoint exposes only status and document summaries. Complete reading content remains in the existing authenticated candidate research view. Candidate evidence never becomes adopted research without the existing review and C3 process.

## Current M5 evidence (2026-09-27)

- Fetchspec local package: `/Users/m5/Downloads/tempfetch/deliveries/nvidia-pipeline-20260927/`.
- Manifest: 449 PDF entries, 934,559,717 bytes total; all 449 files present, sizes match, and SHA identities are unique.
- Language metadata: 23 Chinese, 426 English/unmarked; English classification is not fully verified for 425 unmarked entries.
- Package stores only PDFs, but known source coverage gaps remain; it is not evidence of complete public NVIDIA coverage.
- Local M5 reader: five pilot documents; 3 complete candidate reports, 1 blocked, 1 failed. Complete candidate snapshot contains three documents. This is not full reading of all 449 PDFs.
- The three complete reports were re-exported from the existing M5 catalog with the latest code, then validated against current research graph 2.1.2 and questions 2.2.0: 3 documents, 274 evidence rows, 194 statements. No reread/model call was made.
- Existing candidate snapshot previously reached the research candidate receiver, but no online progress page yet confirmed this new status projection.

## Implementation and verification

`src/inresearch/workflow/pilot_progress.py` validates and stores a candidate-only progress envelope outside the formal research registry. `POST /api/pilot-progress/nvidia` uses a dedicated, narrowly scoped pilot credential (not the Spark Reader credential); `GET` exposes bounded progress summaries. `web/pages/nvidia-pilot.html` presents the pilot with explicit M5/AWS and candidate-only labels. `manage.py publish-pilot-progress` is the M5 publisher. Replayed/older progress is rejected. M5 keeps the credential at `~/.local/state/inresearch.ai/nvidia-pilot.token`; AWS stores its counterpart in `/srv/inresearch.ai/data/.nvidia_pilot_token` (mode 0600), outside Git.

Governance refresh/check, strict data validation, and the pilot/supply/interface unit tests pass. The full 1,341-test unit suite has one unrelated environment failure: the installed Homebrew Node cannot load `simdutf.35.dylib`; the new NVIDIA browser test therefore remains for GitHub CI. A dedicated random pilot credential is installed mode 0600 at M5 `~/.local/state/inresearch.ai/nvidia-pilot.token` and AWS `/srv/inresearch.ai/data/.nvidia_pilot_token`, outside Git and separate from Spark credentials. AWS release SHA/health with this code and the real M5 upload acknowledgement remain pending; do not call the online path delivered until both are checked.
