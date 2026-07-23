# Build-along guide

The complete guided build lives at <https://learn.datalumina.com/docs/invoice-review>. This local guide records the first checkpoint represented by the `main` branch.

## Starter outcome

The repository installs reproducibly, starts a minimal FastAPI service and React interface, and includes the business brief plus fictional source documents.

## Why this boundary exists

The starter removes the completed workflow while preserving every prerequisite needed to build it. You begin with the user, the source documents, and explicit service boundaries instead of reverse-engineering a finished application.

## Commands

```bash
cd backend
uv sync --locked

cd ../frontend
pnpm install --frozen-lockfile

cd ..
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
./scripts/dev.sh --check
./scripts/dev.sh
```

## Important locations

- `docs/client-brief.md`: the recurring finance problem and definition of done
- `docs/architecture.md`: the intended boundaries and data flow
- `samples/`: the fictional evaluation corpus and manifest
- `backend/app/main.py`: the initial API boundary
- `frontend/src/App.tsx`: the initial interface boundary

## What you should observe

- `GET http://localhost:8000/health` returns `{"status":"ok"}`.
- `http://localhost:5173` shows the Invoice Review starter screen.
- No Azure request occurs at this checkpoint.

## Checkpoint

- [ ] Locked backend and frontend installs succeed.
- [ ] Backend lint passes.
- [ ] Frontend type-check, lint, and production build pass.
- [ ] `./scripts/dev.sh --check` reports that Invoice Review is ready to start.
- [ ] The health endpoint and starter screen load locally.

Continue with the [online tutorial](https://learn.datalumina.com/docs/invoice-review).

## Classify uploads before extraction

### Outcome

A pipeline step classifies an unknown PDF or image as `invoice` or `receipt` using Azure OpenAI structured output through Pydantic AI. The result is a typed `DocumentClassification` model you can use to route to `prebuilt-invoice` or `prebuilt-receipt`.

### Why this boundary exists

Document Intelligence has separate extraction models but no reliable prebuilt classifier for invoice vs receipt. Classification happens first with Azure OpenAI on the original document bytes; extraction stays in Document Intelligence afterward.

### Commands

```bash
cd backend
uv sync --locked
uv run --locked --no-sync ruff check app/pipeline

cd ../playground
uv run --project ../backend --locked --no-sync python classify_sample_document.py
uv run --project ../backend --locked --no-sync python classify_sample_document.py ../samples/generated/13-nl-fuel-receipt.png
```

### Important locations

- `backend/app/pipeline/classification.py`: `DocumentClassification` schema and `DocumentClassifier.run()`
- `backend/app/services/azure_openai_service.py`: shared Azure OpenAI settings and deployment name
- `playground/classify_sample_document.py`: manual classifier check against sample documents

### What you should observe

- The sample invoice PDF returns `"document_kind": "invoice"`.
- The Dutch fuel receipt PNG returns `"document_kind": "receipt"`.
- Each response includes a confidence score and short reasoning string.
- This step consumes one Azure OpenAI Responses API call per document.

### Checkpoint

- [ ] `pydantic-ai-slim[openai]` is pinned in `backend/pyproject.toml` and `backend/uv.lock`.
- [ ] Backend lint passes for `app/pipeline`.
- [ ] The playground script classifies the invoice PDF and receipt PNG correctly.
- [ ] You can explain why classification precedes Document Intelligence extraction.

## Chain classify → extract → validate

### Outcome

A typed pipeline chains three steps: classify the upload, call the matching Document Intelligence model (`prebuilt-invoice` or `prebuilt-receipt`), map into Pydantic extraction models, then run offline EU VAT format checks and totals reconciliation. Each step reads and writes a shared `PipelineContext`.

### Why this boundary exists

Azure calls and deterministic finance rules must stay separable. The pipeline only sequences steps; Document Intelligence SDK types are converted to domain models inside the extraction step; VAT and totals live in pure functions under `app/documents/validation.py` so later approval policy can reuse them without calling Azure.

### Commands

```bash
cd backend
uv run --locked --no-sync ruff check app/pipeline app/documents

cd ../playground
uv run --project ../backend --locked --no-sync python run_pipeline.py
uv run --project ../backend --locked --no-sync python run_pipeline.py ../samples/generated/13-nl-fuel-receipt.png
```

### Important locations

- `backend/app/pipeline/base.py`: `PipelineContext`, `PipelineStep`, and `Pipeline`
- `backend/app/pipeline/classification.py`: `ClassificationStep`
- `backend/app/pipeline/extraction.py`: routes invoice vs receipt and maps to Pydantic models
- `backend/app/pipeline/validation.py`: attaches VAT and totals findings to the context
- `backend/app/documents/validation.py`: pure `validate_eu_vat` and `reconcile_totals` helpers
- `playground/run_pipeline.py`: end-to-end manual check

### What you should observe

- The sample invoice classifies as `invoice`, extracts supplier/customer/VAT/dates/PO/totals/line items, and reports VAT/totals findings.
- The Dutch fuel receipt classifies as `receipt`, extracts merchant/transaction/totals via `prebuilt-receipt`, and reconciles receipt totals when amounts are present.
- Invalid present VAT IDs become `vat_invalid` errors; missing amounts become `totals_incomplete` info findings, not silent failures.
- This flow consumes one Azure OpenAI classification call plus one Document Intelligence analyze call per document.

### Checkpoint

- [ ] Backend lint passes for `app/pipeline` and `app/documents`.
- [ ] `run_pipeline.py` routes the invoice PDF and receipt PNG to the correct DI model.
- [ ] Extraction summaries show the core financial fields needed for downstream review.
- [ ] You can explain why validation is pure Python and not part of the Azure adapters.

## Suggest a Northstar GL account

### Outcome

A fourth pipeline step suggests one GL account from a fixed 10-account Northstar catalog using Azure OpenAI structured output through Pydantic AI. The categorizer receives normalized extraction fields for both invoices and receipts and writes a typed `GlSuggestion` onto the shared `PipelineContext`.

### Why this boundary exists

The model may suggest an account, but the catalog owns business policy. Keeping the fixed GL list in `app/accounting/` and the Azure call in `app/pipeline/gl_categorization.py` makes that separation explicit. The categorizer reads extracted fields only, not the original document bytes, so it stays independent from classification and Document Intelligence.

### Commands

```bash
cd backend
uv run --locked --no-sync ruff check app/pipeline app/accounting app/documents

cd ../playground
uv run --project ../backend --locked --no-sync python run_pipeline.py
uv run --project ../backend --locked --no-sync python run_pipeline.py ../samples/generated/13-nl-fuel-receipt.png
```

### Important locations

- `backend/app/accounting/catalog.py`: `GlAccountCode`, `NORTHSTAR_GL_CATALOG`, and prompt formatting
- `backend/app/pipeline/gl_categorization.py`: `GlSuggestion`, `GlCategorizer.run()`, and `GlCategorizationStep`
- `backend/app/pipeline/base.py`: `gl_suggestion` on `PipelineContext`
- `backend/app/pipeline/__init__.py`: registers the step in `build_default_pipeline()`
- `playground/run_pipeline.py`: includes `gl_suggestion` in the JSON output

### What you should observe

- The sample invoice JSON includes `"gl_suggestion"` with `account_code`, `confidence`, and `reasoning`.
- A cleaning-services invoice should suggest `6100`; a fuel receipt should suggest `6170`.
- The suggested code is always one of the ten catalog values (`6100`–`6190`).
- This flow consumes two Azure OpenAI Responses API calls per document: classification and GL suggestion.

### Checkpoint

- [ ] Backend lint passes for `app/pipeline`, `app/accounting`, and `app/documents`.
- [ ] `run_pipeline.py` prints `gl_suggestion` for the invoice PDF and receipt PNG.
- [ ] You can explain why the catalog lives outside the model adapter and why receipts are included.
- [ ] You can explain why GL suggestion runs after extraction and uses normalized fields only.

## Expose the pipeline through FastAPI

### Outcome

A thin HTTP and SQLite layer wraps the proven `build_default_pipeline()` flow. Upload a PDF or image, persist classification, extraction, validation, and GL suggestion, list saved reviews, delete a review, and read the fixed Northstar GL catalog — without corrections, decisions, or correction-email drafts yet.

### Why this boundary exists

Routes own HTTP parsing and status codes. The service owns orchestration (save file → run pipeline → map status). The repository owns SQLite. Persistence and HTTP now wrap known pipeline behavior instead of becoming the place where extraction and policy are invented.

### Commands

```bash
cd backend
uv run --locked --no-sync ruff check app
uv run --locked --no-sync uvicorn app.main:create_app --factory --reload
```

In a second terminal from the repo root:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/accounting/gl-accounts
curl -F \
  "file=@samples/generated/02-nl-happy-compact.pdf;type=application/pdf" \
  http://localhost:8000/api/documents
curl http://localhost:8000/api/documents
```

### Important locations

- `backend/app/main.py`: FastAPI factory, CORS, `/health`
- `backend/app/config.py`: fixed upload/DB/CORS application config
- `backend/app/database.py`: SQLAlchemy engine and session factory
- `backend/app/documents/routes.py`: upload, list, and delete
- `backend/app/documents/service.py`: calls `build_default_pipeline()`
- `backend/app/documents/repository.py` and `models.py`: SQLite persistence
- `backend/app/accounting/routes.py`: `GET /api/accounting/gl-accounts`

### What you should observe

- `GET /health` returns `{"status":"ok"}`.
- `GET /api/accounting/gl-accounts` returns the ten Northstar accounts (`6100`–`6190`).
- One multipart upload returns a persisted review with `classification`, `extraction`, `validation`, and `gl_suggestion`.
- Status is `needs_review` when validation has errors, otherwise `ready`; pipeline failures become `failed` with `502`.
- Oversized (>4 MB) or non-PDF/JPEG/PNG uploads are rejected before Azure is called.
- `DELETE /api/documents/{id}` removes the SQLite row and the local upload file.

### Checkpoint

- [ ] Backend lint passes for `app`.
- [ ] Health, GL catalog, upload, and list work with curl against a running uvicorn process.
- [ ] You can explain why routes, service, and repository stay separate from the pipeline steps.
- [ ] You can explain why corrections, decisions, and correction-email are deferred until later.

## Scaffold the welcome → upload → pipeline UI

### Outcome

The React app boots with a Northstar welcome screen. Maya can choose a PDF/JPEG/PNG, preview it locally, start processing, and see the development pipeline result (`classification`, `extraction`, `validation`, `gl_suggestion`). History lists and deletes saved reviews through the existing FastAPI routes. Field editing, approve/reject, and correction-email remain deferred.

### Why this boundary exists

The frontend stays a thin workflow shell: `env.ts` owns `VITE_API_BASE_URL`, `api.ts` owns `fetch`/`FormData`, and components consume application types that mirror the current `DocumentResponse`. Processing progress is local UI only; the real work is one blocking `POST /api/documents` that already runs `build_default_pipeline()`.

### Commands

```bash
cd frontend
cp .env.example .env
pnpm install --frozen-lockfile
pnpm exec tsc -b --pretty false
pnpm lint
pnpm build
pnpm dev
```

In a second terminal, keep the API running:

```bash
cd backend
uv run --locked --no-sync uvicorn app.main:create_app --factory --reload
```

Open `http://localhost:5173`, choose a sample under `samples/generated/`, and click **Process document**.

### Important locations

- `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/App.tsx`: Vite entry and view machine (`welcome` → `upload` → `processing` → `result` / `history`)
- `frontend/src/lib/env.ts`, `api.ts`, `types.ts`: environment boundary and typed HTTP client for development responses
- `frontend/src/components/WelcomePortal.tsx`, `UploadStep.tsx`, `ProcessingStep.tsx`: welcome, dropzone/preview, and staged progress copy
- `frontend/src/components/PipelineResult.tsx`, `DocumentInbox.tsx`: read-only pipeline summary and history list/delete

### What you should observe

- The welcome screen offers **Review a document** and **View history**.
- Upload accepts PDF/JPEG/PNG up to 4 MB, shows a local preview, and does not call Azure until **Process document**.
- Process switches to the processing view, then lands on a result that shows classification, extraction highlights, validation findings, and the GL suggestion.
- Failed uploads return to the upload step with the API error message (`413`, `415`, `502`, and so on).
- History loads `GET /api/documents` and can delete with `DELETE /api/documents/{id}`.

### Checkpoint

- [ ] Frontend type-check, lint, and production build pass.
- [ ] With the API running, you can upload a sample and see a persisted pipeline result in the browser.
- [ ] You can explain why the UI types follow development `DocumentResponse` instead of the solution’s flattened review model.
- [ ] You can explain why corrections, decisions, and correction-email stay out of this slice.

## Close the Maya review loop

### Outcome

Maya can upload a sample, inspect the prepared review, correct fields, confirm a Northstar GL account, approve or reject, and draft a supplier correction email when supplier-fixable issues exist. Document Intelligence stays primary; an independent Azure OpenAI review fills gaps and exposes provenance. Northstar policy issue codes match `samples/manifest.json`.

### Why this boundary exists

The cleaner `documents/` + `pipeline/` layout stays intact. Solution behavior is ported as:

- a flat `ReviewData` projection for policy and edits
- pure validation that emits manifest issue codes
- review APIs under `/api/documents`
- LLM merge in `document_review/` + a pipeline step
- correction-email eligibility as a small pure package

Stage JSON columns remain for teaching; the interactive UI reads `review_data`, `issues`, `document_review`, and `accounting_coding`.

### Commands

```bash
# Backend
cd backend
rm -f data/documents.db   # recreate schema after model changes
uv run --locked --no-sync ruff check app scripts
uv run --locked --no-sync uvicorn app.main:create_app --factory --reload

# Optional live corpus checks (Azure usage)
uv run --locked --no-sync python scripts/evaluate_corpus.py
uv run --locked --no-sync python scripts/evaluate_hybrid.py

# Frontend
cd frontend
pnpm exec tsc -b --pretty false
pnpm lint
pnpm build
pnpm dev
```

Manual demo set: `02-nl-happy-compact.pdf` (approve), `06-de-invalid-vendor-vat.pdf` (edit or reject), `08-en-total-mismatch.pdf` (totals error), `13-nl-fuel-receipt.png` (receipt), and `10-de-duplicate.pdf` after `03-de-happy-modern.pdf` (duplicate).

### Important locations

- `backend/app/documents/validation.py`, `projection.py`, `schemas.py`, `service.py`, `routes.py`
- `backend/app/pipeline/document_review.py`, `validation.py`
- `backend/app/document_review/reconciliation.py`
- `backend/app/correction_email/`
- `backend/app/providers/azure_openai_document_review.py`, `azure_openai_correction_email.py`
- `frontend/src/components/DocumentReview.tsx`, `DocumentReviewSection.tsx`, `CorrectionEmailDialog.tsx`
- `frontend/src/lib/api.ts`, `types.ts`, `review-outcome.ts`

### What you should observe

- Happy-path samples land as `ready` with empty issue lists (PO present).
- Sample `05` reports `vendor_vat_id_required`; `06` reports `vendor_vat_id_invalid`; `07` reports `customer_vat_id_mismatch`; `08` reports `invoice_total_mismatch`; `09` reports warning `purchase_order_missing` but stays `ready`.
- Saving field corrections re-runs policy and can clear errors.
- Approve requires a selected GL and no error issues; decided reviews lock editing.
- Rejected reviews with supplier-fixable issues can open a Copy/Close correction-email draft.

### Checkpoint

- [ ] Backend lint passes for `app` and `scripts`.
- [ ] Frontend type-check, lint, and production build pass.
- [ ] You can approve a clean sample and reject a broken one in the browser.
- [ ] You can explain why Document Intelligence remains primary over the LLM fallback.
- [ ] Corpus evaluator field accuracy is high and policy codes match the manifest (except duplicate, which needs a peer in SQLite).

## Deploy a single container to Azure

### Outcome

The FastAPI API and React SPA run as one container in Azure Container Apps inside `rg-invoice-review`, with SQLite/uploads on Azure Files and a shared-password login gate so a public URL cannot freely burn Azure quota.

### Why this boundary exists

Local development stays two processes (`./scripts/dev.sh`). Production collapses to one origin so cookies and relative API calls stay simple. Auth is one shared password plus an HMAC session cookie — not accounts or Entra for the app itself. Provider calls still use API keys from Container App secrets.

### Commands

See [azure-deploy.md](azure-deploy.md) for the full `az` sequence. Summary:

```bash
# Confirm context
az account show
az group show --name rg-invoice-review

# Build image in ACR, create Files share + Container Apps env/app
# (exact resource names and secret wiring are in azure-deploy.md)

# Local verification before/without Azure
cd backend && uv run --locked --no-sync ruff check app scripts
cd ../frontend && pnpm exec tsc -b --pretty false && pnpm lint && VITE_API_BASE_URL=/ pnpm build
```

### Important locations

- `Dockerfile`, `.dockerignore`
- `backend/app/main.py` (static SPA + password middleware)
- `backend/app/auth/`
- `backend/app/config.py` (`APP_ACCESS_PASSWORD`, `APP_SESSION_SECRET`, `ALLOWED_ORIGIN`, `FRONTEND_DIST_DIR`)
- `frontend/src/components/LoginPage.tsx`, `frontend/src/App.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/env.ts`
- `docs/azure-deploy.md`

### What you should observe

- `GET /health` returns `{"status":"ok"}` without a cookie.
- `GET /api/documents` returns `401` until you sign in with the shared password.
- After login, the familiar upload → process → review flow works on the Container App HTTPS URL.
- Restarting the Container App revision does not wipe SQLite/uploads when `/app/data` is mounted from Azure Files.

### Checkpoint

- [ ] Backend lint and frontend type-check/lint/build pass.
- [ ] Container image builds (`az acr build` or local Docker).
- [ ] Deployed `/health` is open; API is gated; browser login unlocks a sample upload.
- [ ] You can tear down hosting resources without deleting the whole resource group.
