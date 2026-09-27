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
- Existing candidate snapshot previously reached the research candidate receiver, but no online progress page yet confirmed this new status projection.

## Implementation and verification

`src/inresearch/workflow/pilot_progress.py` validates and stores a candidate-only progress envelope outside the formal research registry. `POST /api/pilot-progress/nvidia` uses the existing restricted machine credential; `GET` exposes bounded progress summaries. `web/pages/nvidia-pilot.html` presents the pilot with explicit M5/AWS and candidate-only labels. `manage.py publish-pilot-progress` is the M5 publisher. Replayed/older progress is rejected.

Automated test outcomes, browser inspection, AWS release SHA/health, and real M5 upload acknowledgement must be filled in before calling the online path delivered. Until then, this document records an implementation proposal/acceptance boundary, not a successful production release.
