# Free Local Voice Clone - one-step installer for Windows.
#
# Run it from PowerShell:
#   irm https://raw.githubusercontent.com/waseemnasir2k26/free-local-voice-clone/main/install-windows.ps1 -OutFile $env:TEMP\vc-install.ps1
#   powershell -ExecutionPolicy Bypass -File $env:TEMP\vc-install.ps1
#
# What it does (everything goes into one folder, default C:\voiceclone):
#   1. checks disk space and your graphics card
#   2. finds Python (installs 3.12 with winget if you have none)
#   3. downloads the audio.cpp runtime (about 1.1 GB) and the Higgs model (5.1 GB)
#   4. installs this tool into its own private Python environment
#   5. writes voiceclone.cmd so you can run it with no setup, and runs a self-check
#
# Safe to run again: finished downloads are skipped, interrupted ones resume.
# By downloading the model you accept the Boson Higgs TTS 3 licence:
#   https://huggingface.co/bosonai/higgs-tts-3-4b/blob/main/LICENSE

param(
    [string]$Dir = "C:\voiceclone",
    [string]$ModelPath = "",       # already have the .gguf? pass its full path to skip the 5.1 GB download
    [switch]$NoPath                # do not add the install folder to your PATH
)

# Windows PowerShell turns any text a program prints on stderr into an error, so do not stop
# on those. Every step below checks its own exit code instead.
$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

$Ver       = "v0.9.2"   # the audio.cpp version this tool was tested with
$Rel       = "https://github.com/0xShug0/audio.cpp/releases/download/$Ver"
$ModelName = "higgs-audio-v3-tts-4b-q8_0.gguf"
$ModelUrl  = "https://huggingface.co/audio-cpp/audio.cpp-gguf/resolve/main/Higgs-Audio-v3-TTS-4B-GGUF/$ModelName"
$ModelSize = 5095359136
$Package   = "local-voice-clone[qc] @ https://github.com/waseemnasir2k26/free-local-voice-clone/archive/refs/heads/main.zip"

function Step($msg) { Write-Host "`n== $msg" -ForegroundColor Cyan }
function Stop-Install($msg) { Write-Host "`nSTOPPED: $msg" -ForegroundColor Red; exit 1 }

function Get-File($url, $out, [long]$size) {
    # $size = exact expected bytes, or a negative number meaning "at least this many"
    if (Test-Path $out) {
        $have = (Get-Item $out).Length
        if (($size -gt 0 -and $have -eq $size) -or ($size -lt 0 -and $have -ge -$size)) {
            Write-Host "   already downloaded: $(Split-Path $out -Leaf)"
            return
        }
    }
    Write-Host "   downloading $(Split-Path $out -Leaf) ..."
    & curl.exe -L --fail --retry 8 --retry-delay 5 -C - -o $out $url
    if ($LASTEXITCODE -ne 0) {
        Stop-Install "download failed: $url`n   Check your internet and run this installer again. It continues where it stopped."
    }
    $have = (Get-Item $out).Length
    if ($size -gt 0 -and $have -ne $size) {
        Remove-Item $out -Force
        Stop-Install "$(Split-Path $out -Leaf) is the wrong size ($have bytes). It was removed. Run the installer again."
    }
}

function Find-Python {
    foreach ($v in "3.12", "3.11", "3.13", "3.10") {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            & cmd.exe /c "py -$v -c `"import sys`" >nul 2>nul"
            if ($LASTEXITCODE -eq 0) { return @("py", "-$v") }
        }
    }
    foreach ($p in "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
                   "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
                   "$env:ProgramFiles\Python312\python.exe") {
        if (Test-Path $p) { return @($p) }
    }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notlike "*WindowsApps*") {
        & cmd.exe /c "python -c `"import sys; raise SystemExit(0 if (3,10) <= sys.version_info[:2] <= (3,13) else 1)`" >nul 2>nul"
        if ($LASTEXITCODE -eq 0) { return @("python") }
    }
    return $null
}

Write-Host "Free Local Voice Clone installer" -ForegroundColor Green
Write-Host "Install folder: $Dir"

# ---------------------------------------------------------------- 1. checks
Step "1/6 Checking this computer"
if ($Dir -match "\s") { Stop-Install "the install folder must not contain spaces. Use something like C:\voiceclone" }
New-Item -ItemType Directory -Force -Path $Dir, "$Dir\downloads", "$Dir\audiocpp", "$Dir\models", "$Dir\voices" -ErrorAction Stop | Out-Null
$drive = (Get-Item $Dir).PSDrive
$needGb = if ($ModelPath) { 5 } else { 12 }
$freeGb = [math]::Round($drive.Free / 1GB, 1)
Write-Host "   free disk space on $($drive.Name): $freeGb GB (need about $needGb GB)"
if ($freeGb -lt $needGb) { Stop-Install "not enough free disk space. Free up at least $needGb GB on drive $($drive.Name):" }

$backend = "vulkan"
$cards = @(Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue | ForEach-Object { $_.Name })
$nvidia = $cards | Where-Object { $_ -match "NVIDIA" } | Select-Object -First 1
if ($nvidia) {
    $backend = "cuda"
    Write-Host "   graphics card: $nvidia"
    $vram = 0
    if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
        foreach ($try in 1..3) {   # a sleeping laptop GPU can fail the first query
            $lines = @(& nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits)
            if ($LASTEXITCODE -eq 0 -and $lines.Count -gt 0 -and "$($lines[0])".Trim() -match "^\d+$") {
                $vram = [int]("$($lines[0])".Trim()); break
            }
            Start-Sleep -Seconds 2
        }
    }
    if ($vram -gt 0) { Write-Host "   video memory: $vram MB" }
    if ($vram -gt 0 -and $vram -lt 7000) {
        Write-Host "   WARNING: less than 8 GB of video memory. It may run slowly or run out of memory." -ForegroundColor Yellow
    }
    if ($vram -eq 0) {
        Write-Host "   WARNING: could not read the NVIDIA driver. Update your graphics driver if voicing fails." -ForegroundColor Yellow
    }
}
if ($backend -eq "vulkan") {
    Write-Host "   No NVIDIA card found. Installing the Vulkan build (AMD / Intel)." -ForegroundColor Yellow
    Write-Host "   This path is NOT tested by us. It may be slow. Please report what happens." -ForegroundColor Yellow
}

# ---------------------------------------------------------------- 2. python
Step "2/6 Finding Python"
$py = Find-Python
if (-not $py) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Stop-Install "Python is not installed. Install Python 3.12 from https://www.python.org/downloads/ (tick 'Add python.exe to PATH'), then run this installer again."
    }
    Write-Host "   Python not found. Installing Python 3.12 with winget ..."
    & winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
    $py = Find-Python
    if (-not $py) { Stop-Install "Python was installed but this window cannot see it yet. Close PowerShell, open it again, and run the installer again." }
}
Write-Host "   using: $($py -join ' ')"

# ---------------------------------------------------------------- 3. runtime
Step "3/6 Downloading the audio.cpp runtime ($Ver, $backend)"
if ($backend -eq "cuda") {
    Get-File "$Rel/audio-$Ver-bin-windows-x64-cuda12.4.zip"    "$Dir\downloads\audiocpp-bin.zip"    463532839
    Get-File "$Rel/audio-$Ver-cudart-windows-x64-cuda12.4.zip" "$Dir\downloads\audiocpp-cudart.zip" 607273675
    $zips = "audiocpp-bin.zip", "audiocpp-cudart.zip"
} else {
    Get-File "$Rel/audio-$Ver-bin-windows-x64-vulkan.zip" "$Dir\downloads\audiocpp-vulkan.zip" -20000000
    $zips = @("audiocpp-vulkan.zip")
}
foreach ($z in $zips) {
    Write-Host "   unpacking $z ..."
    $winTar = "$env:SystemRoot\System32\tar.exe"   # the Windows one; other tars on PATH misread C:\ paths
    if (Test-Path $winTar) {
        & $winTar -xf "$Dir\downloads\$z" -C "$Dir\audiocpp"
    } else {
        Expand-Archive -Path "$Dir\downloads\$z" -DestinationPath "$Dir\audiocpp" -Force
        $LASTEXITCODE = if ($?) { 0 } else { 1 }
    }
    if ($LASTEXITCODE -ne 0) { Stop-Install "could not unpack $z. Delete $Dir\downloads\$z and run the installer again." }
}
if (-not (Test-Path "$Dir\audiocpp\audiocpp_cli.exe")) { Stop-Install "audiocpp_cli.exe is missing after unpacking." }

# ---------------------------------------------------------------- 4. model
Step "4/6 The voice model (5.1 GB, the long step)"
if ($ModelPath) {
    if (-not (Test-Path $ModelPath)) { Stop-Install "-ModelPath does not exist: $ModelPath" }
    $model = (Resolve-Path $ModelPath).Path
    Write-Host "   using your existing model: $model"
} else {
    $model = "$Dir\models\$ModelName"
    Get-File $ModelUrl $model $ModelSize
}

# ---------------------------------------------------------------- 5. the tool
Step "5/6 Installing the voiceclone tool"
$venvPy = "$Dir\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    $pyArgs = @()
    if ($py.Count -gt 1) { $pyArgs = $py[1..($py.Count - 1)] }
    & $py[0] @pyArgs -m venv "$Dir\.venv"
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPy)) { Stop-Install "could not create the Python environment." }
}
& $venvPy -m pip install --quiet --upgrade pip
& $venvPy -m pip install --quiet --upgrade --force-reinstall --no-deps $Package
if ($LASTEXITCODE -ne 0) { Stop-Install "could not download the tool from GitHub. Check your internet and run the installer again." }
& $venvPy -m pip install --quiet $Package
if ($LASTEXITCODE -ne 0) { Stop-Install "could not install the Python packages. Check your internet and run the installer again." }

$launcher = @"
@echo off
rem Free Local Voice Clone launcher. Written by install-windows.ps1.
set "AUDIOCPP_CLI=$Dir\audiocpp\audiocpp_cli.exe"
set "HIGGS_GGUF=$model"
if not defined VOICECLONE_VOICES set "VOICECLONE_VOICES=$Dir\voices"
"$venvPy" -m voiceclone %*
"@
Set-Content -Path "$Dir\voiceclone.cmd" -Value $launcher -Encoding ASCII

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not $NoPath -and ($userPath -split ";") -notcontains $Dir) {
    [Environment]::SetEnvironmentVariable("Path", ($userPath.TrimEnd(";") + ";" + $Dir), "User")
    Write-Host "   added $Dir to your PATH (new PowerShell windows can run: voiceclone)"
}

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "   installing ffmpeg (needed to cut your voice sample) ..."
        & winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) { Write-Host "   ffmpeg did not install. Install it later: winget install Gyan.FFmpeg" -ForegroundColor Yellow }
    } else {
        Write-Host "   ffmpeg not found. Install it from https://ffmpeg.org before using 'voiceclone ref'." -ForegroundColor Yellow
    }
}

# ---------------------------------------------------------------- 6. check
Step "6/6 Self-check"
& "$Dir\voiceclone.cmd" doctor
if ($LASTEXITCODE -ne 0) { Stop-Install "the self-check failed. Copy everything above and send it to whoever shared this with you." }

Write-Host "`nINSTALLED." -ForegroundColor Green
Write-Host "Close this window, open a NEW PowerShell window, then:"
Write-Host "   cd $Dir"
Write-Host "   voiceclone ref --in C:\path\to\my-recording.m4a --start 5 --dur 15 --name me"
Write-Host "   voiceclone say --voice me `"This is my voice. I never recorded this sentence.`" -o test.wav"
Write-Host "Only clone your own voice, or a voice you have written permission to use."
