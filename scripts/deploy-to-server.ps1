# SigmaTrade Bot - PowerShell Deployment Script
# Deploys latest code from main branch to production server

$ErrorActionPreference = "Stop"

# Configuration - UPDATE THESE VALUES
$INSTANCE_NAME = "sigmatrade-20251108-210354"
$ZONE = "europe-north1-a"
$PROJECT_ID = "telegram-bot-444304"
$PROJECT_PATH = "/opt/sigmatradebot"
$GIT_BRANCH = "main"
$GIT_REPO = "https://github.com/Avertenandor/sigmatradebot2.git"

Write-Host "╔═══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   SigmaTrade Bot - Server Deployment                 ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Step 1: Copy deployment script to server
Write-Host "[1/4] Copying deployment script to server..." -ForegroundColor Green
$scriptPath = Join-Path $PSScriptRoot "deploy-update.sh"
$remoteScriptPath = "/tmp/deploy-update.sh"

gcloud compute scp $scriptPath "${INSTANCE_NAME}:${remoteScriptPath}" `
    --zone=$ZONE `
    --project=$PROJECT_ID

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to copy script to server" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Script copied" -ForegroundColor Green

# Step 2: Make script executable and run deployment
Write-Host "[2/4] Running deployment on server..." -ForegroundColor Green

$deployCommand = @"
cd ${PROJECT_PATH} && \
chmod +x ${remoteScriptPath} && \
${remoteScriptPath}
"@

gcloud compute ssh $INSTANCE_NAME `
    --zone=$ZONE `
    --project=$PROJECT_ID `
    --command=$deployCommand

if ($LASTEXITCODE -ne 0) {
    Write-Host "Deployment failed" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Deployment completed" -ForegroundColor Green

# Step 3: Check service status
Write-Host "[3/4] Checking service status..." -ForegroundColor Green

$statusCommand = @"
cd ${PROJECT_PATH} && \
docker-compose -f docker-compose.python.yml ps
"@

gcloud compute ssh $INSTANCE_NAME `
    --zone=$ZONE `
    --project=$PROJECT_ID `
    --command=$statusCommand

# Step 4: Show recent logs
Write-Host "[4/4] Showing recent logs..." -ForegroundColor Green

$logsCommand = @"
cd ${PROJECT_PATH} && \
echo '=== Bot Logs (last 30 lines) ===' && \
docker-compose -f docker-compose.python.yml logs bot --tail 30 && \
echo '' && \
echo '=== Worker Logs (last 20 lines) ===' && \
docker-compose -f docker-compose.python.yml logs worker --tail 20 && \
echo '' && \
echo '=== Scheduler Logs (last 20 lines) ===' && \
docker-compose -f docker-compose.python.yml logs scheduler --tail 20
"@

gcloud compute ssh $INSTANCE_NAME `
    --zone=$ZONE `
    --project=$PROJECT_ID `
    --command=$logsCommand

Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║           Deployment Complete!                      ║" -ForegroundColor Green
Write-Host "╚═══════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "To view live logs, run:" -ForegroundColor Yellow
Write-Host "  gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID" -ForegroundColor Yellow
Write-Host "  cd $PROJECT_PATH" -ForegroundColor Yellow
Write-Host "  docker-compose -f docker-compose.python.yml logs -f bot" -ForegroundColor Yellow

