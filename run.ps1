# Published stack for Windows. Does not build an image or install an editor.
param(
    [switch]$Open
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

foreach ($arg in $args) {
    if ($arg -eq "--build" -or $arg -eq "-Build") {
        Write-Host "The published start does not build. Use ./run-dev.sh"
        Write-Host "ERROR startup_failed reason_code=build_refused"
        exit 1
    }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR startup_failed reason_code=docker_missing"
    exit 1
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR startup_failed reason_code=daemon_down"
    exit 1
}
Write-Host "INFO startup_docker_ok"

if ([string]::IsNullOrWhiteSpace($env:PALIMPSEST_API_IMAGE)) {
    $Image = "ghcr.io/deliium/palimpsest:0.1.0"
} else {
    $Image = $env:PALIMPSEST_API_IMAGE
}
if ([string]::IsNullOrWhiteSpace($env:PALIMPSEST_API_PUBLISH_PORT)) {
    $Port = "8080"
} else {
    $Port = $env:PALIMPSEST_API_PUBLISH_PORT
}
$Url = "http://127.0.0.1:$Port/"

Write-Host "INFO startup_pull_started image=$Image"
docker compose -f compose.yaml pull
if ($LASTEXITCODE -ne 0) {
    Write-Host "The release image is unavailable. Contributors can start with ./run-dev.sh"
    Write-Host "ERROR startup_failed reason_code=pull_failed"
    exit 1
}

docker compose -f compose.yaml up -d --wait --wait-timeout 180
if ($LASTEXITCODE -ne 0) {
    docker compose -f compose.yaml ps --all
    docker compose -f compose.yaml logs --no-color --tail 80 api
    Write-Host "ERROR startup_failed reason_code=health_timeout"
    exit 1
}

Write-Host "Observer: $Url"
Write-Host "INFO startup_ready url=$Url"
if ($Open) {
    Start-Process $Url
}
