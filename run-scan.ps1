#Requires -Version 5.1
<#
.SYNOPSIS
    Start the demo MCP server, run the scanner against it, and print the result.

.DESCRIPTION
    - Starts `uv run main.py` in mcp-sever-demo\ in the background.
    - Waits until port 8000 accepts TCP connections (max 30 s).
    - Runs `uv run main.py` in scanner\ and shows its output.
    - Always stops the server again (including on Ctrl+C) and cleans up logs.
    - Exits with the scanner's exit code.

.EXAMPLE
    .\run-scan.ps1

.EXAMPLE
    # Forward arguments to the scanner
    .\run-scan.ps1 --json
#>
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $ScannerArgs = @()
)

$ErrorActionPreference = 'Stop'

$root       = $PSScriptRoot
$serverDir  = Join-Path $root 'mcp-sever-demo'
$scannerDir = Join-Path $root 'scanner'
$port       = 8000
$url        = "http://localhost:$port/mcp"

# --- Helpers --------------------------------------------------------------
function Test-Port {
    param(
        [string] $TargetHost = '127.0.0.1',
        [int]    $TargetPort,
        [int]    $TimeoutMs = 300
    )
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $iar = $client.BeginConnect($TargetHost, $TargetPort, $null, $null)
        if (-not $iar.AsyncWaitHandle.WaitOne($TimeoutMs)) { return $false }
        $client.EndConnect($iar)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Stop-ServerTree {
    param([int] $ProcessId)

    $started = [datetime]::UtcNow
    if ($ProcessId -gt 0) {
        & taskkill /PID $ProcessId /T /F 2>$null | Out-Null
    }

    # Fallback: kill whatever still owns the port (handles a uv wrapper
    # whose python child outlived it).
    if (Test-Port -TargetPort $port) {
        $owner = (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
                  Select-Object -First 1).OwningProcess
        if ($owner) {
            & taskkill /PID $owner /T /F 2>$null | Out-Null
        }
    }

    # Give Windows a moment to release the socket.
    while ((Test-Port -TargetPort $port) -and ([datetime]::UtcNow - $started).TotalSeconds -lt 5) {
        Start-Sleep -Milliseconds 200
    }
}

# --- Pre-flight -----------------------------------------------------------
foreach ($required in @($serverDir, $scannerDir)) {
    if (-not (Test-Path $required)) {
        Write-Host "Missing folder: $required" -ForegroundColor Red
        exit 1
    }
}

$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvCommand) {
    Write-Host 'uv was not found on PATH. Install it from https://docs.astral.sh/uv/' -ForegroundColor Red
    exit 1
}
$uv = $uvCommand.Source

if (Test-Port -TargetPort $port) {
    Write-Host "Port $port is already in use. Stop that process first." -ForegroundColor Red
    exit 1
}

$outLog = Join-Path ([IO.Path]::GetTempPath()) ("mcp-server-{0}.out.log" -f [guid]::NewGuid())
$errLog = Join-Path ([IO.Path]::GetTempPath()) ("mcp-server-{0}.err.log" -f [guid]::NewGuid())
$server = $null
$status = 1

try {
    # --- Start the server -------------------------------------------------
    Write-Host "Starting demo MCP server ($url) ..."
    $server = Start-Process -FilePath $uv `
        -ArgumentList @('run', 'main.py') `
        -WorkingDirectory $serverDir `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError $errLog `
        -WindowStyle Hidden `
        -PassThru

    # --- Wait until it accepts connections --------------------------------
    Write-Host -NoNewline 'Waiting for the server '
    $ready = $false
    for ($i = 1; $i -le 60; $i++) {
        if (Test-Port -TargetPort $port) { $ready = $true; break }

        if ($server.HasExited) {
            Write-Host ''
            Write-Host ("Server exited before the port opened (exit code {0}). Log:" -f $server.ExitCode) -ForegroundColor Red
            if (Test-Path $errLog) { Get-Content $errLog | Out-Host }
            if (Test-Path $outLog) { Get-Content $outLog | Out-Host }
            exit 1
        }
        Write-Host -NoNewline '.'
        Start-Sleep -Milliseconds 500
    }

    if (-not $ready) {
        Write-Host ''
        Write-Host "Timed out waiting for port $port. Log:" -ForegroundColor Red
        if (Test-Path $errLog) { Get-Content $errLog | Out-Host }
        if (Test-Path $outLog) { Get-Content $outLog | Out-Host }
        exit 1
    }
    Write-Host 'up.'

    # --- Run the scanner --------------------------------------------------
    Write-Host ''
    Write-Host '===== SCANNER OUTPUT ====='
    Push-Location $scannerDir
    try {
        & $uv run main.py @ScannerArgs
        $status = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    Write-Host '=========================='
    Write-Host "Scanner exited with code $status"
}
finally {
    if ($server) {
        if (-not $server.HasExited) {
            Stop-ServerTree -ProcessId $server.Id
        } else {
            # uv may have exited while its python child kept the port.
            Stop-ServerTree -ProcessId 0
        }
    }
    Remove-Item $outLog, $errLog -Force -ErrorAction SilentlyContinue
}

exit $status
