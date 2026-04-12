param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$InputPath
)

Write-Host 'GPX Wrapper for MakerBot Replicator 2'
Write-Host 'This script injects necessary Start G-code for the Replicator 2'

$ErrorActionPreference = 'Stop'

function Invoke-InjectGpxBlock {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $false)]
        [string]$NozzleTemp = '200'
    )

    $lines = @(Get-Content -LiteralPath $Path)

    $startIndex = -1
    $endIndex = -1

    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match 'GPX_START_MARKER') {
            $startIndex = $i
            break
        }
    }

    if ($startIndex -lt 0) {
        return 10
    }

    for ($i = $startIndex + 1; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match 'GPX_END_MARKER') {
            $endIndex = $i
            break
        }
    }

    if ($endIndex -lt 0) {
        return 11
    }

    $inject = @(
        '; --- GPX_START_MARKER ---',
        '; ====== START GCODE FOR MAKERBOT REPLICATOR 2 ======',
        '',
        '; --- Full homing using endstops ---',
        'G162 X Y F3000        ; Home XY to MAX endstops (rear/right)',
        'G161 Z F1200          ; Home Z to MIN endstop (platform up)',
        '',
        '; --- Origin consistent with MAX homing ---',
        'G92 X285 Y152 Z0      ; R2: X=285, Y=152',
        '',
        'G1 Z5 F1200           ; Raise a bit to avoid contact',
        '',
        '; --- Nozzle heating ---',
        ('M104 S' + $NozzleTemp),
        'M6 T0                 ; Wait for nozzle to heat',
        '',
        '; --- Extruder preparation ---',
        'G92 E0                ; Reset extrusion',
        '',
        '; ====== PURGE LINE ======',
        'G1 X5 Y5 Z0.3 F3000   ; Move to front-left corner',
        'G1 E8 F200            ; Extrude a bit',
        'G1 X120 Y5 F1500      ; Draw purge line',
        'G92 E0                ; Reset extrusion',
        '; ====== END PURGE LINE ======',
        '',
        '; --- GPX_END_MARKER ---'
    )

    $newLines = @()

    if ($startIndex -gt 0) {
        $newLines += $lines[0..($startIndex - 1)]
    }

    $newLines += $inject

    if ($endIndex + 1 -le $lines.Count - 1) {
        $newLines += $lines[($endIndex + 1)..($lines.Count - 1)]
    }

    Set-Content -LiteralPath $Path -Value $newLines -Encoding Ascii
    return 0
}

$baseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtimeDir = $baseDir

if (Test-Path -LiteralPath 'C:\msys64\ucrt64\bin\libiconv-2.dll') {
    $runtimeDir = 'C:\msys64\ucrt64\bin'
}

$env:PATH = "$runtimeDir;$env:PATH"

$gpxExe = Join-Path $baseDir 'gpx.exe'

$intermediateX3g = Join-Path $env:TEMP ("gpxwrap_{0}_{1}.x3g" -f (Get-Random), (Get-Random))

$success = $true
$errorMessage = ''
$alreadyConverted = $false
$prusaGcodePath = $null

try {
    if (-not (Test-Path -LiteralPath $InputPath)) {
        throw "Input file does not exist: $InputPath"
    }

    if ($InputPath -match '(?i)\.gcode\.pp$') {
        $prusaGcodePath = $InputPath -replace '(?i)\.pp$', ''
    }

    if (-not (Test-Path -LiteralPath $gpxExe)) {
        throw "Unable to find GPX: $gpxExe"
    }

    $firstLayerTemp = '200'
    $tempLine = Select-String -Path $InputPath -Pattern '^M10[49]\s+S(?<temp>\d+)' -CaseSensitive:$false | Select-Object -First 1
    if ($tempLine -and $tempLine.Matches.Count -gt 0) {
        $matchTemp = $tempLine.Matches[0].Groups['temp'].Value
        if ($matchTemp) {
            $firstLayerTemp = $matchTemp
        }
    }

    $injectStatus = Invoke-InjectGpxBlock -Path $InputPath -NozzleTemp $firstLayerTemp

    if ($injectStatus -eq 10) {
        $alreadyConverted = $true
    }

    if ($injectStatus -eq 11) {
        $alreadyConverted = $true
    }

    if ($injectStatus -ne 0 -and -not $alreadyConverted) {
        throw "Unable to inject Start G-code into: $InputPath"
    }

    if ($alreadyConverted) {
        Write-Host 'GPX markers not found; file may already be converted. Injection skipped.'
        Write-Host ''
    }

    if (-not $alreadyConverted) {
        & $gpxExe -m r2 $InputPath $intermediateX3g
        if ($LASTEXITCODE -ne 0) {
            throw 'GPX failed during conversion.'
        }

        if (-not (Test-Path -LiteralPath $intermediateX3g)) {
            throw 'GPX did not generate the .x3g file'
        }

        Copy-Item -LiteralPath $intermediateX3g -Destination $InputPath -Force
        if (-not (Test-Path -LiteralPath $InputPath)) {
            throw "Unable to replace content of: $InputPath"
        }
    }

    if ($prusaGcodePath) {
        $inputFullPath = [System.IO.Path]::GetFullPath($InputPath)
        $gcodeFullPath = [System.IO.Path]::GetFullPath($prusaGcodePath)
        if ($inputFullPath -ne $gcodeFullPath -and (Test-Path -LiteralPath $prusaGcodePath)) {
            Remove-Item -LiteralPath $prusaGcodePath -Force -ErrorAction SilentlyContinue
        }
    }

    Write-Host ("Source file replaced with X3G binary: {0}" -f $InputPath)
}
catch {
    $success = $false
    $errorMessage = $_.Exception.Message
}
finally {
    Remove-Item -LiteralPath $intermediateX3g -Force -ErrorAction SilentlyContinue
}

if (-not $success) {
    Write-Host "ERROR: $errorMessage"
    Write-Host ''
    exit 1
}

exit 0
