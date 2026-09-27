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
- The 2026-09-27 M5-to-AWS publish was acknowledged with `ok: true` for 3 documents. AWS storage reports the envelope as available, candidate-only, with 5 documents total: 3 complete, 1 blocked, 1 failed; its three titles match the complete NVIDIA reports above.

## Implementation and verification

`src/inresearch/workflow/pilot_progress.py` validates and stores a candidate-only progress envelope outside the formal research registry. `POST /api/pilot-progress/nvidia` uses a dedicated, narrowly scoped pilot credential (not the Spark Reader credential); `GET` exposes bounded progress summaries. `web/pages/nvidia-pilot.html` presents the pilot with explicit M5/AWS and candidate-only labels. `manage.py publish-pilot-progress` is the M5 publisher. Replayed/older progress is rejected. M5 keeps the credential at `~/.local/state/inresearch.ai/nvidia-pilot.token`; AWS stores its counterpart in `/srv/inresearch.ai/data/.nvidia_pilot_token` (mode 0600), outside Git.

PR #235 (conflict resolution and mobile header fix) and PR #238 (publisher and runtime credential-path fix) are merged. AWS reports healthy release `96dceb9c5e3646958c9c6b83138a7f5344e5ed89`. The real M5 upload received an `ok: true` acknowledgement for 3 documents, and a read-only projection check inside the AWS container confirmed the stored candidate-only counts and titles. The online page is [NVIDIA 产品资料验证](https://inresearch.ai/nvidia-pilot.html) and requires a normal signed-in session; the endpoint does not expose progress anonymously. The pilot is live via M5 → AWS without Spark.

The M5 token at `~/.local/state/inresearch.ai/nvidia-pilot.token` and AWS counterpart at `/srv/inresearch.ai/data/.nvidia_pilot_token` are mode 0600, outside Git and separate from Spark credentials. The first accepted envelope has no server `received_at` timestamp, so the page currently displays “接收于未知”; PR #240 adds an AWS file-write-time fallback. The entire 449-PDF package has not been read; only the five-document pilot was processed. Candidate content remains in its separate runtime projection and is not automatically inserted into formal research or treated as adopted evidence. Spark permanent storage, scheduling, and formal evidence review remain later work.
