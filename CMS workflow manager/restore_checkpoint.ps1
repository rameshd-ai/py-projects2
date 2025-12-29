# Restore Checkpoint Script
# Usage: .\restore_checkpoint.ps1 checkpoint_name

param(
    [Parameter(Mandatory=$true)]
    [string]$CheckpointName
)

$checkpointPath = "checkpoints\$CheckpointName"

if (-not (Test-Path $checkpointPath)) {
    Write-Host "Error: Checkpoint '$CheckpointName' not found!" -ForegroundColor Red
    Write-Host "Available checkpoints:" -ForegroundColor Yellow
    Get-ChildItem -Path "checkpoints" -Directory | ForEach-Object { Write-Host "  - $($_.Name)" }
    exit 1
}

Write-Host "Restoring checkpoint: $CheckpointName" -ForegroundColor Green
Write-Host "Warning: This will overwrite current files!" -ForegroundColor Yellow
$confirm = Read-Host "Continue? (yes/no)"

if ($confirm -ne "yes") {
    Write-Host "Restore cancelled." -ForegroundColor Yellow
    exit 0
}

# Restore Python files
Write-Host "Restoring Python files..." -ForegroundColor Cyan
Get-ChildItem -Path "$checkpointPath\*.py" | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination "." -Force
    Write-Host "  Restored: $($_.Name)" -ForegroundColor Gray
}

# Restore templates
if (Test-Path "$checkpointPath\templates") {
    Write-Host "Restoring templates..." -ForegroundColor Cyan
    Remove-Item -Path "templates\*" -Recurse -Force -ErrorAction SilentlyContinue
    Copy-Item -Path "$checkpointPath\templates\*" -Destination "templates\" -Recurse -Force
    Write-Host "  Templates restored" -ForegroundColor Gray
}

# Restore processing_steps
if (Test-Path "$checkpointPath\processing_steps") {
    Write-Host "Restoring processing_steps..." -ForegroundColor Cyan
    Remove-Item -Path "processing_steps\*.py" -Force -ErrorAction SilentlyContinue
    Copy-Item -Path "$checkpointPath\processing_steps\*.py" -Destination "processing_steps\" -Force
    Write-Host "  Processing steps restored" -ForegroundColor Gray
}

Write-Host "`nCheckpoint restored successfully!" -ForegroundColor Green
Write-Host "Please restart the server to apply changes." -ForegroundColor Yellow




