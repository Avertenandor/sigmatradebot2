# PowerShell script to deploy admin management system to server
# This script connects to server and runs deployment

$ErrorActionPreference = "Stop"

Write-Host "╔═══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║    Deploy Admin Management System to Server          ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Configuration
$INSTANCE_NAME = "sigmatrade-20251108-210354"
$ZONE = "europe-north1-a"
$PROJECT = "telegram-bot-444304"
$DEPLOY_SCRIPT = "/tmp/deploy-admin-system.sh"

# Step 1: Copy deployment script to server
Write-Host "[Step 1/3] Copying deployment script to server..." -ForegroundColor Green
$scriptPath = Join-Path $PSScriptRoot "deploy-admin-system.sh"
if (-not (Test-Path $scriptPath)) {
    Write-Host "ERROR: Deployment script not found: $scriptPath" -ForegroundColor Red
    exit 1
}

Write-Host "Uploading script to server..." -ForegroundColor Yellow
gcloud compute scp $scriptPath "${INSTANCE_NAME}:${DEPLOY_SCRIPT}" `
    --zone=$ZONE `
    --project=$PROJECT

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to upload script" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Script uploaded" -ForegroundColor Green

# Step 2: Make script executable and run it
Write-Host ""
Write-Host "[Step 2/3] Running deployment on server..." -ForegroundColor Green
Write-Host "This will:" -ForegroundColor Yellow
Write-Host "  - Update code from repository" -ForegroundColor Yellow
Write-Host "  - Apply database migration" -ForegroundColor Yellow
Write-Host "  - Rebuild and restart services" -ForegroundColor Yellow
Write-Host ""

$confirm = Read-Host "Continue? (y/N)"
if ($confirm -ne "y" -and $confirm -ne "Y") {
    Write-Host "Deployment cancelled" -ForegroundColor Yellow
    exit 0
}

Write-Host "Executing deployment script on server..." -ForegroundColor Yellow
gcloud compute ssh $INSTANCE_NAME `
    --zone=$ZONE `
    --project=$PROJECT `
    --command="chmod +x ${DEPLOY_SCRIPT} && ${DEPLOY_SCRIPT}"

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Deployment failed!" -ForegroundColor Red
    exit 1
}

# Step 3: Verify deployment
Write-Host ""
Write-Host "[Step 3/3] Verifying deployment..." -ForegroundColor Green
Write-Host "Checking container status..." -ForegroundColor Yellow

gcloud compute ssh $INSTANCE_NAME `
    --zone=$ZONE `
    --project=$PROJECT `
    --command="cd /opt/sigmatradebot && docker-compose -f docker-compose.python.yml ps"

Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║           Deployment Complete!                       ║" -ForegroundColor Green
Write-Host "╚═══════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Test admin panel: Send /admin in Telegram" -ForegroundColor White
Write-Host "  2. Check logs: docker-compose logs -f bot" -ForegroundColor White
Write-Host "  3. Verify migration: alembic current" -ForegroundColor White
Write-Host ""
Write-Host "⚠️  IMPORTANT: All admins will need to enter master key on first login!" -ForegroundColor Yellow

