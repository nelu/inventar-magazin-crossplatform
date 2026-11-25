<#
.SYNOPSIS
Build the reusable Windows toolchain, then compile a release executable without starting the GUI.
.PARAMETER ToolingOnly
Prepare the image only, including the selected cache seed. No application sources are required.
.PARAMETER ToolingImage
Use a prepared local Docker image and skip building the tooling image.
.PARAMETER BaseImage
Override the daemon-build-specific LTSC MSVC image.
.PARAMETER Isolation
hyperv (default) or process; process requires a compatible host and image.
.PARAMETER CacheVolume
Persistent Docker volume name. A new volume starts with the image's standalone cache seed.
.PARAMETER CacheDirectory
Optional host directory (relative to this script or absolute) to mount instead of the cache volume.
.PARAMETER ReleasePath
Windows x64 executable output, relative to this script or absolute; defaults to dist\Magazin.release.exe.
The existing file at this path is replaced atomically only on success.
#>
[CmdletBinding()]
param(
    [switch] $ToolingOnly,
    [string] $ToolingImage,
    [string] $BaseImage,
    [ValidateSet('hyperv', 'process')] [string] $Isolation = 'hyperv',
    [ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9_.-]+$')] [string] $CacheVolume = 'magazin-nuitka-cache',
    [string] $CacheDirectory,
    [Alias('CandidatePath')] [string] $ReleasePath = 'dist\Magazin.release.exe'
)
$ErrorActionPreference = 'Stop'
$info = docker info --format '{{json .}}' | ConvertFrom-Json
$kernel = "$($info.OSType) $($info.KernelVersion)"
if ($LASTEXITCODE -or $kernel -notmatch '^windows 10\.0[. ](\d+)') { throw "Windows Docker daemon required (got '$kernel')" }
$hostBuild = [int]$Matches[1]
if (-not $ToolingImage -and -not $BaseImage) {
    $repo = 'amitie10g/visualstudio2022-workload-vctools'
    if ($hostBuild -in 20348, 22000, 22621, 22631, 26100, 26200) { # Server 2022 / newer hosts, Hyper-V
        $BaseImage = "${repo}:ltsc2022"
    } elseif ($hostBuild -in 17763, 18362, 18363, 19041, 19042, 19043, 19044, 19045) { # LTSC 2019
        $BaseImage = "${repo}:ltsc2019"
    } else { throw "Unrecognized Windows host build $hostBuild. Specify -BaseImage with a compatible LTSC MSVC image." }
}
Write-Host "Daemon build $hostBuild; isolation $Isolation; daemon NCPU $($info.NCPU)"
$oldBuildKit = $env:DOCKER_BUILDKIT
$image = if ($ToolingImage) { $ToolingImage } else { 'magazin-tooling:windows' }
$container = $null
$staging = $null
Push-Location $PSScriptRoot
try {
    if ($ToolingImage) {
        docker image inspect $image | Out-Null
        if ($LASTEXITCODE) { throw "Prepared tooling image is not available locally: $image" }
    } else {
        # Use the classic builder for Windows containers.
        $env:DOCKER_BUILDKIT = '0'
        $labels = @()
        if ($env:MAGAZIN_TOOLING_FINGERPRINT) {
            $labels += '--label', "io.magazin.tooling.fingerprint=$env:MAGAZIN_TOOLING_FINGERPRINT"
        }
        if ($env:MAGAZIN_TOOLING_SOURCE) {
            $labels += '--label', "org.opencontainers.image.source=$env:MAGAZIN_TOOLING_SOURCE"
        }
        Write-Host "Tooling image $image; base $BaseImage"
        docker build --pull --force-rm --isolation $Isolation --build-arg "BUILD_TOOLS_IMAGE=$BaseImage" `
            --target tooling --tag $image --file Dockerfile.windows @labels .
        if ($LASTEXITCODE) { throw "Docker build failed ($LASTEXITCODE)" }
    }
    if ($ToolingOnly) { return }

    $cacheMount = "type=volume,source=$CacheVolume,target=C:\nuitka-cache"
    if ($CacheDirectory) {
        $cachePath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($CacheDirectory)
        [void][IO.Directory]::CreateDirectory($cachePath)
        $cacheMount = "type=bind,source=$cachePath,target=C:\nuitka-cache"
    }
    Write-Host "Compile image $image; cache mount $cacheMount"
    $exe = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($ReleasePath)
    if ([IO.Path]::GetExtension($exe) -ne '.exe') { throw 'ReleasePath must end in .exe' }
    $dist = [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($exe))
    $staging = New-Item -ItemType Directory (Join-Path $dist.FullName ('.build-' + [guid]::NewGuid()))
    $tempExe = Join-Path $staging.FullName 'Magazin.exe'
    $container = docker create --isolation $Isolation `
        --mount $cacheMount `
        --mount "type=bind,source=$PSScriptRoot,target=C:\app,readonly" `
        $image
    if ($LASTEXITCODE) { throw "docker create failed ($LASTEXITCODE)" }
    docker start $container | Out-Null
    if ($LASTEXITCODE) { throw "Could not start compile container ($LASTEXITCODE)" }
    do {
        $state = docker inspect --format '{{json .State}}' $container | ConvertFrom-Json
        if ($LASTEXITCODE) { throw "Could not inspect compile container ($LASTEXITCODE)" }
        if ($state.Running) { Start-Sleep -Seconds 1 }
    } while ($state.Running)
    docker logs --tail 2000 $container
    if ($LASTEXITCODE) { throw "Could not read compile container logs ($LASTEXITCODE)" }
    if ($state.Status -ne 'exited' -or $state.ExitCode) {
        throw "Compile container $($state.Status) (exit $($state.ExitCode)): $($state.Error)"
    }
    docker cp "${container}:C:/out/Magazin.exe" $tempExe
    if ($LASTEXITCODE) { throw "docker cp failed ($LASTEXITCODE)" }

    $size = (Get-Item -LiteralPath $tempExe).Length
    $hash = (Get-FileHash -LiteralPath $tempExe).Hash
    if ([IO.File]::Exists($exe)) { [IO.File]::Replace($tempExe, $exe, [System.Management.Automation.Language.NullString]::Value) }
    else { [IO.File]::Move($tempExe, $exe) }
    Write-Host "Windows x64 executable: $exe ($size bytes); SHA256 $hash"
} finally {
    if ($container) { docker rm -f $container | Out-Null }
    if ($staging) { Remove-Item -LiteralPath $staging.FullName -Recurse -Force }
    $env:DOCKER_BUILDKIT = $oldBuildKit
    Pop-Location
}
