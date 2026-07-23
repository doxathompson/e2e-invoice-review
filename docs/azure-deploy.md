# Azure single-container deploy

Deploy the FastAPI + React app as one container into the existing resource group `rg-invoice-review` (West Europe) using Azure Container Apps.

## What gets created

| Resource | Name | Purpose |
| --- | --- | --- |
| Container Registry | `acrinvreviewweu` | Holds the image |
| Storage account | `stinvreviewweu` | Azure Files for SQLite + uploads |
| File share | `invoice-review-data` | Mounted at `/app/data` |
| Environment storage | `invoice-review-files` | Binds the share into Container Apps |
| Container Apps Environment | `cae-invoice-review` | Hosting environment |
| Container App | `ca-invoice-review` | The running app |
| Log Analytics | `workspace-rginvoicereviewWSiH` | Created with the environment |

Reuse the existing Document Intelligence and Foundry resources in the same group. Do not recreate them.

## Tier and standing cost

| Resource | Tier | Notes |
| --- | --- | --- |
| ACR | Basic | Small monthly fee while it exists |
| Container Apps | Consumption | Pay while replicas run; min replicas `1` for the first demo |
| Storage + Azure Files | Standard LRS | Tiny share for SQLite/uploads |
| Log Analytics | Pay-as-you-go | Often created with the environment |

The app uses a shared access password (`APP_ACCESS_PASSWORD`) so a public URL cannot freely burn Document Intelligence and OpenAI quota. This is not enterprise auth.

## Prerequisites

```bash
az account show
az group show --name rg-invoice-review
```

Local secrets for the image (never commit):

- From `backend/.env`: Document Intelligence and Azure OpenAI endpoint/key/deployment
- Generate a demo password and session secret:

```bash
APP_ACCESS_PASSWORD="$(openssl rand -base64 18)"
APP_SESSION_SECRET="$(openssl rand -hex 32)"
```

## Build and push the image

Pick a globally unique ACR name (alphanumeric only). This deployment uses `acrinvreviewweu`:

```bash
RG=rg-invoice-review
LOCATION=westeurope
ACR_NAME=acrinvreviewweu

az acr create \
  --resource-group "$RG" \
  --name "$ACR_NAME" \
  --sku Basic \
  --location "$LOCATION"

az acr build \
  --registry "$ACR_NAME" \
  --resource-group "$RG" \
  --image invoice-review:latest \
  .
```

`az acr build` builds the root `Dockerfile` in Azure (no local Docker daemon required).

## Persistent storage

```bash
STORAGE_NAME=stinvreviewweu
SHARE_NAME=invoice-review-data

az storage account create \
  --resource-group "$RG" \
  --name "$STORAGE_NAME" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --kind StorageV2

STORAGE_KEY="$(az storage account keys list \
  --resource-group "$RG" \
  --account-name "$STORAGE_NAME" \
  --query "[0].value" -o tsv)"

az storage share create \
  --account-name "$STORAGE_NAME" \
  --account-key "$STORAGE_KEY" \
  --name "$SHARE_NAME"
```

## Container Apps environment and app

```bash
ENV_NAME=cae-invoice-review
APP_NAME=ca-invoice-review

az containerapp env create \
  --resource-group "$RG" \
  --name "$ENV_NAME" \
  --location "$LOCATION"

# Load provider values from backend/.env (do not paste keys into shell history docs).
# Required env names:
#   AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT
#   AZURE_DOCUMENT_INTELLIGENCE_KEY
#   AZURE_OPENAI_ENDPOINT
#   AZURE_OPENAI_DEPLOYMENT
#   AZURE_OPENAI_API_KEY
#   APP_ACCESS_PASSWORD
#   APP_SESSION_SECRET

az containerapp create \
  --resource-group "$RG" \
  --name "$APP_NAME" \
  --environment "$ENV_NAME" \
  --image "$ACR_NAME.azurecr.io/invoice-review:latest" \
  --registry-server "$ACR_NAME.azurecr.io" \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 1 \
  --cpu 0.5 \
  --memory 1.0Gi \
  --secrets \
    di-key="$AZURE_DOCUMENT_INTELLIGENCE_KEY" \
    openai-key="$AZURE_OPENAI_API_KEY" \
    access-password="$APP_ACCESS_PASSWORD" \
    session-secret="$APP_SESSION_SECRET" \
    storage-key="$STORAGE_KEY" \
  --env-vars \
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT="$AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT" \
    AZURE_DOCUMENT_INTELLIGENCE_KEY=secretref:di-key \
    AZURE_OPENAI_ENDPOINT="$AZURE_OPENAI_ENDPOINT" \
    AZURE_OPENAI_DEPLOYMENT="$AZURE_OPENAI_DEPLOYMENT" \
    AZURE_OPENAI_API_KEY=secretref:openai-key \
    APP_ACCESS_PASSWORD=secretref:access-password \
    APP_SESSION_SECRET=secretref:session-secret \
    ALLOWED_ORIGIN=https://PLACEHOLDER.azurecontainerapps.io \
    FRONTEND_DIST_DIR=/app/frontend/dist \
  --system-assigned

# Attach Azure Files after create (volume + mount):
az containerapp update \
  --resource-group "$RG" \
  --name "$APP_NAME" \
  --set-env-vars ALLOWED_ORIGIN="https://$(az containerapp show -g "$RG" -n "$APP_NAME" --query properties.configuration.ingress.fqdn -o tsv)"

az containerapp show \
  --resource-group "$RG" \
  --name "$APP_NAME" \
  --query properties.configuration.ingress.fqdn -o tsv
```

Mount the file share (YAML-style update is the reliable CLI path):

```bash
# Export current app YAML, add volume + volumeMount under the container,
# then apply with: az containerapp update -g "$RG" -n "$APP_NAME" --yaml app.yaml
#
# volume:
#   name: data
#   storageName: invoice-review-files   # storage definition on the environment
# volumeMount:
#   volumeName: data
#   mountPath: /app/data
```

Register the Azure Files storage on the environment first:

```bash
az containerapp env storage set \
  --resource-group "$RG" \
  --name "$ENV_NAME" \
  --storage-name invoice-review-files \
  --azure-file-account-name "$STORAGE_NAME" \
  --azure-file-account-key "$STORAGE_KEY" \
  --azure-file-share-name "$SHARE_NAME" \
  --access-mode ReadWrite
```

Then add the volume and `/app/data` mount on the Container App (via `az containerapp update --yaml` or the portal). The container workdir is `/app`, and SQLite/uploads use `./data`.

Enable ACR pull for the system-assigned identity:

```bash
PRINCIPAL_ID="$(az containerapp show -g "$RG" -n "$APP_NAME" --query identity.principalId -o tsv)"
ACR_ID="$(az acr show -g "$RG" -n "$ACR_NAME" --query id -o tsv)"
az role assignment create \
  --assignee "$PRINCIPAL_ID" \
  --role AcrPull \
  --scope "$ACR_ID"
```

Or use admin credentials on first create:

```bash
az acr update -n "$ACR_NAME" --admin-enabled true
ACR_USER="$(az acr credential show -n "$ACR_NAME" --query username -o tsv)"
ACR_PASS="$(az acr credential show -n "$ACR_NAME" --query passwords[0].value -o tsv)"
```

Pass `--registry-username` / `--registry-password` to `az containerapp create` when not using managed identity pull yet.

## Verify

```bash
FQDN="$(az containerapp show -g rg-invoice-review -n ca-invoice-review --query properties.configuration.ingress.fqdn -o tsv)"

curl -s "https://$FQDN/health"
# {"status":"ok"}

curl -s -o /dev/null -w "%{http_code}\n" "https://$FQDN/api/documents"
# 401

# Browser: open https://$FQDN , sign in with APP_ACCESS_PASSWORD, upload a sample.
```

## Cleanup (hosting only — keep DI and Foundry)

```bash
az containerapp delete --resource-group rg-invoice-review --name ca-invoice-review --yes
az containerapp env delete --resource-group rg-invoice-review --name cae-invoice-review --yes
az acr delete --resource-group rg-invoice-review --name acrinvreviewweu --yes
az storage account delete --resource-group rg-invoice-review --name stinvreviewweu --yes
az monitor log-analytics workspace delete --resource-group rg-invoice-review --workspace-name workspace-rginvoicereviewWSiH --yes
```

Do not run `az group delete` unless you explicitly intend to remove Document Intelligence and Foundry as well.
