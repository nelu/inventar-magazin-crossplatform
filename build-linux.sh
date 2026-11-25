#!/usr/bin/env bash
set -euo pipefail

tooling_only=false
case $#:$* in
    0:) ;;
    1:--tooling-only) tooling_only=true ;;
    *) printf 'Usage: %s [--tooling-only]\n' "$0" >&2; exit 2 ;;
esac

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
source_dir=$(pwd -P)
if command -v cygpath >/dev/null 2>&1; then
    source_dir=$(cygpath -am "$source_dir")
    # Git Bash must not translate paths inside Docker's Linux containers.
    export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'
fi

if ! daemon_os=$(docker info --format '{{.OSType}}') || [[ $daemon_os != linux ]]; then
    echo 'A Linux Docker engine is required. On Docker Desktop, switch to Linux containers.' >&2
    exit 1
fi

image=${MAGAZIN_TOOLING_IMAGE:-magazin-tooling:linux}
cache=${NUITKA_CACHE_VOLUME:-magazin-nuitka-cache-linux-x64}
artifact=Magazin-linux-x64
release=dist/$artifact.release
if [[ -z ${MAGAZIN_TOOLING_IMAGE:-} ]]; then
    labels=()
    if [[ -n ${MAGAZIN_TOOLING_FINGERPRINT:-} ]]; then
        labels+=(--label "io.magazin.tooling.fingerprint=$MAGAZIN_TOOLING_FINGERPRINT")
    fi
    if [[ -n ${MAGAZIN_TOOLING_SOURCE:-} ]]; then
        labels+=(--label "org.opencontainers.image.source=$MAGAZIN_TOOLING_SOURCE")
    fi
    docker build --pull --platform linux/amd64 --tag "$image" --file Dockerfile.linux "${labels[@]}" .
else
    docker image inspect "$image" >/dev/null
fi
if $tooling_only; then exit 0; fi

cache_mount="type=volume,source=$cache,target=/nuitka-cache"
if [[ -n ${NUITKA_CACHE_DIRECTORY:-} ]]; then
    mkdir -p -- "$NUITKA_CACHE_DIRECTORY"
    cache_dir=$(cd -- "$NUITKA_CACHE_DIRECTORY" && pwd -P)
    if command -v cygpath >/dev/null 2>&1; then cache_dir=$(cygpath -am "$cache_dir"); fi
    cache_mount="type=bind,source=$cache_dir,target=/nuitka-cache"
fi

container=
staging=
cleanup() {
    if [[ -n $container ]]; then docker rm -f "$container" >/dev/null || true; fi
    if [[ -n $staging ]]; then rm -rf -- "$staging"; fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

container=$(docker create --platform linux/amd64 \
    --mount "type=bind,source=$source_dir,target=/app,readonly" \
    --mount "$cache_mount" \
    "$image")
docker start "$container" >/dev/null
while [[ $(docker inspect --format '{{.State.Running}}' "$container") == true ]]; do
    sleep 1
done
docker logs --tail 2000 "$container"
state=$(docker inspect --format '{{.State.Status}} {{.State.ExitCode}}' "$container")
if [[ $state != 'exited 0' ]]; then
    echo "Linux build container: $state" >&2
    exit 1
fi

mkdir -p -- dist
staging=$(mktemp -d dist/.build-linux-XXXXXXXX)
binary=$staging/$artifact
docker cp "$container:/out/$artifact" "$binary"

# ELF magic, 64-bit little-endian class, ET_EXEC or ET_DYN (PIE), EM_X86_64.
read -r -a header <<< "$(od -An -v -tx1 -N20 -w20 -- "$binary")"
if [[ ${header[*]:0:6} != '7f 45 4c 46 02 01' ||
      ( ${header[16]:-} != 02 && ${header[16]:-} != 03 ) || ${header[17]:-} != 00 ||
      ${header[18]:-} != 3e || ${header[19]:-} != 00 ]]; then
    echo 'Expected an x86-64 Linux ELF executable.' >&2
    exit 1
fi
chmod +x -- "$binary"
checksum=$(sha256sum -- "$binary")
mv -fT -- "$binary" "$release"
printf 'Validated x86-64 ELF: %s; SHA256 %s\n' "$release" "${checksum%% *}"
