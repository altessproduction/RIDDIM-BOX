#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
# Build the RIDDIM ROOTS web emulator: firmware sources -> wasm32, then copy
# the web shell + icons next to the wasm.
#   CC="python3 -m ziglang cc" sh build.sh     (any wasm32-capable driver works)
set -e
cd "$(dirname "$0")"
ROOT=$(cd .. && pwd)

CC=${CC:-clang}
CFLAGS=${CFLAGS:---target=wasm32-freestanding -O2 -fno-builtin -ffreestanding -nostdlib \
    -Wall -Wno-unused-function -Wno-unused-variable -Wno-error=date-time}
LDFLAGS=${LDFLAGS:--Wl,--no-entry -Wl,--export-memory \
    -Wl,-z,stack-size=1048576 -Wl,--global-base=1048576}

test -f "$ROOT/build/gen/felucca_tables.h" || {
    echo "en-tetes generes manquants; lance d'abord les outils gen_*.py dans $ROOT" >&2
    exit 1
}

mkdir -p dist
$CC $CFLAGS -I "$ROOT/build/gen" -I "$ROOT/firmware/src" -I "$ROOT/firmware/hal" \
    $LDFLAGS -o dist/riddim.wasm sloop_wasm.c

cp index.html emu.js worklet.js manifest.webmanifest dist/
cp icon-192.png icon-512.png apple-touch-icon.png dist/ 2>/dev/null || true

# garde la copie Pages a jour
if [ -d "$ROOT/dub" ]; then
    cp dist/riddim.wasm "$ROOT/dub/riddim.wasm"
    cp index.html emu.js worklet.js manifest.webmanifest "$ROOT/dub/"
    cp icon-192.png icon-512.png apple-touch-icon.png "$ROOT/dub/" 2>/dev/null || true
fi
ls -la dist/
