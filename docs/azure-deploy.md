# Azure single-container deploy

Deploy the FastAPI + React app as **one container** into an existing resource group that already has Document Intelligence and Azure OpenAI / Foundry. Hosting is Azure Container Apps + Azure Files for SQLite/uploads.

This guide is written so a human or agent can reproduce the deploy with Azure CLI. Exact resource names below match the teaching deploy; learners must pick **globally unique** ACR and storage account names when those collide.

## What you need before starting

1. Azure CLI logged in to the right subscription: `az account show`
2. An existing resource group with:
   - Document Intelligence (e.g. F0)
   - Azure OpenAI / Foundry with a chat deployment (this project uses `gpt-5.6-terra`)
3. Local `backend/.env` filled with those provider endpoints and keys (never commit it)
4. Repo root as the working directory (Dockerfile lives there)
5. No local Docker required: use `az acr build`

Do **not** recreate Document Intelligence or Foundry here. Do **not** delete the whole resource group for cleanup.

## What gets created (hosting only)

| Resource | Example name | Purpose |
| --- | --- | --- |
| Container Registry | `acrinvreviewweu` | Image store (name must be globally unique, alphanumeric) |
| Storage account | `stinvreviewweu` | Azure Files account (globally unique) |
| File share | `invoice-review-data` | SQLite DB + uploaded files |
| Log Analytics | auto-created with the env | Container Apps logs |
| Container Apps Environment | `cae-invoice-review` | Hosting environment |
| Environment storage | `invoice-review-files` | Binds the file share into the env |
| Container App | `ca-invoice-review` | Running app |

## Tier / cost (state before provisioning)

| Resource | Tier | Notes |
| --- | --- | --- |
| ACR | Basic | Standing monthly fee while it exists |
| Container Apps | Consumption | Pay while replicas run; keep **min=max=1** (SQLite on Azure Files does not tolerate multi-replica writes) |
| Storage + Azure Files | Standard LRS | Tiny share |
| Log Analytics | Pay-as-you-go | Created with the environment unless you pass an existing workspace |

App access uses a shared password (`APP_ACCESS_PASSWORD`) + session cookie secret. Provider auth stays API keys in Container App secrets.

## 0. Set names and load secrets

```bash
cd /path/to/invoice-review   # repo root

RG=rg-invoice-review
LOCATION=westeurope
ACR_NAME=acrinvreviewweu          # change if taken
STORAGE_NAME=stinvreviewweu       # change if taken
SHARE_NAME=invoice-review-data
ENV_NAME=cae-invoice-review
APP_NAME=ca-invoice-review
STORAGE_DEF=invoice-review-files

az account show
az group show --name "$RG"

# Provider config from local env (never commit)
set -a
source backend/.env
set +a

# Required from backend/.env:
#   AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT
#   AZURE_DOCUMENT_INTELLIGENCE_KEY
#   AZURE_OPENAI_ENDPOINT
#   AZURE_OPENAI_DEPLOYMENT
#   AZURE_OPENAI_API_KEY

# Shared app password gate
APP_ACCESS_PASSWORD="$(openssl rand -base64 18)"
APP_SESSION_SECRET="$(openssl rand -hex 32)"
# Save APP_ACCESS_PASSWORD somewhere safe; you need it to sign in.

# Normalize OpenAI base URL to .../openai/v1/
OPENAI_EP="$AZURE_OPENAI_ENDPOINT"
case "$OPENAI_EP" in
  */openai/v1|*/openai/v1/) ;;
  */) OPENAI_EP="${OPENAI_EP}openai/v1/" ;;
  *) OPENAI_EP="${OPENAI_EP}/openai/v1/" ;;
esac
```

## 1. Create ACR and build the image

```bash
az acr create \
  --resource-group "$RG" \
  --name "$ACR_NAME" \
  --sku Basic \
  --location "$LOCATION"

az acr update --name "$ACR_NAME" --admin-enabled true

# Quote the JMESPath for zsh
ACR_USER="$(az acr credential show -n "$ACR_NAME" --query username -o tsv)"
ACR_PASS="$(az acr credential show -n "$ACR_NAME" --query 'passwords[0].value' -o tsv)"

az acr build \
  --registry "$ACR_NAME" \
  --resource-group "$RG" \
  --image invoice-review:latest \
  .
```

The root `Dockerfile` builds the React SPA with `VITE_API_BASE_URL=/`, then runs uvicorn serving API + static files on port `8000`.

## 2. Create storage account + file share

```bash
az storage account create \
  --resource-group "$RG" \
  --name "$STORAGE_NAME" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --kind StorageV2

STORAGE_KEY="$(az storage account keys list \
  --resource-group "$RG" \
  --account-name "$STORAGE_NAME" \
  --query '[0].value' -o tsv)"

az storage share create \
  --account-name "$STORAGE_NAME" \
  --account-key "$STORAGE_KEY" \
  --name "$SHARE_NAME"
```

## 3. Create Container Apps environment + bind Azure Files

```bash
az containerapp env create \
  --resource-group "$RG" \
  --name "$ENV_NAME" \
  --location "$LOCATION"
# Provisioning can sit in Waiting for several minutes. Poll until Succeeded:
# az containerapp env show -g "$RG" -n "$ENV_NAME" --query properties.provisioningState -o tsv

az containerapp env storage set \
  --resource-group "$RG" \
  --name "$ENV_NAME" \
  --storage-name "$STORAGE_DEF" \
  --azure-file-account-name "$STORAGE_NAME" \
  --azure-file-account-key "$STORAGE_KEY" \
  --azure-file-share-name "$SHARE_NAME" \
  --access-mode ReadWrite
```

## 4. Create the Container App (secrets + env + ACR login)

Keys and password go in **Secrets**. Endpoints and deployment name go in plain **environment variables** (visible under Containers → Environment variables in the portal).

```bash
az containerapp create \
  --resource-group "$RG" \
  --name "$APP_NAME" \
  --environment "$ENV_NAME" \
  --image "$ACR_NAME.azurecr.io/invoice-review:latest" \
  --registry-server "$ACR_NAME.azurecr.io" \
  --registry-username "$ACR_USER" \
  --registry-password "$ACR_PASS" \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 1 \
  --cpu 0.5 \
  --memory 1.0Gi \
  --secrets \
    "di-key=$AZURE_DOCUMENT_INTELLIGENCE_KEY" \
    "openai-key=$AZURE_OPENAI_API_KEY" \
    "access-password=$APP_ACCESS_PASSWORD" \
    "session-secret=$APP_SESSION_SECRET" \
  --env-vars \
    "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=$AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT" \
    "AZURE_DOCUMENT_INTELLIGENCE_KEY=secretref:di-key" \
    "AZURE_OPENAI_ENDPOINT=$OPENAI_EP" \
    "AZURE_OPENAI_DEPLOYMENT=${AZURE_OPENAI_DEPLOYMENT:-gpt-5.6-terra}" \
    "AZURE_OPENAI_API_KEY=secretref:openai-key" \
    "APP_ACCESS_PASSWORD=secretref:access-password" \
    "APP_SESSION_SECRET=secretref:session-secret" \
    "FRONTEND_DIST_DIR=/app/frontend/dist"

FQDN="$(az containerapp show -g "$RG" -n "$APP_NAME" --query properties.configuration.ingress.fqdn -o tsv)"
echo "App URL: https://$FQDN"

az containerapp update \
  --resource-group "$RG" \
  --name "$APP_NAME" \
  --set-env-vars "ALLOWED_ORIGIN=https://$FQDN"
```

Portal map:

- **Settings → Secrets** → API keys, access password, session secret, ACR password
- **Application → Containers → Environment variables** → endpoints, deployment name, `ALLOWED_ORIGIN`, secret refs

## 5. Mount Azure Files at `/app/data`

SQLite and uploads use `./data` under the container workdir `/app`. Mount the share there after create.

```bash
# Export current app JSON, add volume + volumeMount, write YAML, apply
az containerapp show -g "$RG" -n "$APP_NAME" -o json > /tmp/ca-app.json

python3 <<'PY'
import json
from pathlib import Path

doc = json.loads(Path("/tmp/ca-app.json").read_text())
props = doc["properties"]
template = props["template"]
container = template["containers"][0]
container["volumeMounts"] = [{"volumeName": "data", "mountPath": "/app/data"}]
template["volumes"] = [{
    "name": "data",
    "storageType": "AzureFile",
    "storageName": "invoice-review-files",
}]

def emit(obj, indent=0):
    sp = "  " * indent
    if isinstance(obj, dict):
        lines = []
        for k, v in obj.items():
            if v is None:
                continue
            if isinstance(v, (dict, list)):
                lines.append(f"{sp}{k}:")
                lines.append(emit(v, indent + 1))
            elif isinstance(v, bool):
                lines.append(f"{sp}{k}: {str(v).lower()}")
            elif isinstance(v, (int, float)):
                lines.append(f"{sp}{k}: {v}")
            else:
                s = str(v)
                if any(c in s for c in ":#{}[]&*!|>'\"%@`") or s == "" or s.lower() in ("true", "false", "null"):
                    s = json.dumps(s)
                lines.append(f"{sp}{k}: {s}")
        return "\n".join(lines)
    if isinstance(obj, list):
        lines = []
        for item in obj:
            if isinstance(item, (dict, list)):
                inner = emit(item, indent + 1).splitlines()
                if not inner:
                    continue
                lines.append(f"{sp}- {inner[0].lstrip()}")
                for extra in inner[1:]:
                    lines.append(extra)
            elif isinstance(item, bool):
                lines.append(f"{sp}- {str(item).lower()}")
            elif isinstance(item, (int, float)):
                lines.append(f"{sp}- {item}")
            else:
                s = json.dumps(str(item)) if any(c in str(item) for c in ":#") else str(item)
                lines.append(f"{sp}- {s}")
        return "\n".join(lines)
    return f"{sp}{obj}"

minimal = {
    "location": doc["location"],
    "type": "Microsoft.App/containerApps",
    "properties": {
        "managedEnvironmentId": props["managedEnvironmentId"],
        "configuration": props["configuration"],
        "template": template,
    },
}
Path("/tmp/ca-app.yaml").write_text(emit(minimal) + "\n")
print("wrote /tmp/ca-app.yaml")
PY

az containerapp update \
  --resource-group "$RG" \
  --name "$APP_NAME" \
  --yaml /tmp/ca-app.yaml

# Keep a single replica. Multiple replicas against one SQLite file on Azure Files
# can crash with: sqlite3.OperationalError: database is locked
az containerapp show -g "$RG" -n "$APP_NAME" \
  --query "{fqdn:properties.configuration.ingress.fqdn,volumes:properties.template.volumes,mounts:properties.template.containers[0].volumeMounts,scale:properties.template.scale}" -o json
```

If the portal shows a **failed revision** while the app still works: traffic is on an older healthy revision (`latestReadyRevisionName`). Deactivate or ignore the crashed revision after fixing scale/mount. Do not assume Overview “Running” means every revision is healthy.

## 6. Verify

```bash
FQDN="$(az containerapp show -g "$RG" -n "$APP_NAME" --query properties.configuration.ingress.fqdn -o tsv)"

curl -s "https://$FQDN/health"
# {"status":"ok"}

curl -s -o /dev/null -w "%{http_code}\n" "https://$FQDN/api/documents"
# 401

curl -s -c /tmp/ir-cookies.txt -b /tmp/ir-cookies.txt \
  -H "Content-Type: application/json" \
  -d "{\"password\":\"$APP_ACCESS_PASSWORD\"}" \
  "https://$FQDN/api/auth/login"
# {"auth_enabled":true,"authenticated":true}

# Browser: https://$FQDN → sign in → upload a sample invoice/receipt
# Optional: restart the active revision and confirm history still lists the document (Files mount).
```

## 7. App behavior reminders (for agents)

- Image serves SPA + API from one origin; frontend build uses `VITE_API_BASE_URL=/`.
- Auth is optional locally (unset password). Deploy **must** set `APP_ACCESS_PASSWORD` and `APP_SESSION_SECRET`.
- `/health` stays open without a cookie; all other `/api/*` require the session when password is set.
- Local `./scripts/dev.sh` is unchanged (two processes, no password).

## Cleanup (hosting only — keep DI and Foundry)

```bash
az containerapp delete --resource-group "$RG" --name "$APP_NAME" --yes
az containerapp env delete --resource-group "$RG" --name "$ENV_NAME" --yes
az acr delete --resource-group "$RG" --name "$ACR_NAME" --yes
az storage account delete --resource-group "$RG" --name "$STORAGE_NAME" --yes
# Delete the Log Analytics workspace created for the environment if present, e.g.:
# az monitor log-analytics workspace delete -g "$RG" --workspace-name workspace-rginvoicereviewWSiH --yes
```

Do **not** run `az group delete` unless you explicitly intend to remove Document Intelligence and Foundry as well.
