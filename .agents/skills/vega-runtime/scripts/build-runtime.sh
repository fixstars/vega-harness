#!/usr/bin/env bash
# Provision a self-contained Python runtime for offline / unknown-Python
# customer machines, using python-build-standalone (the same distributions
# uv installs) plus this skill's pinned dependencies.
#
# Run on a machine of the TARGET OS (binaries are not cross-buildable):
#   bash scripts/build-runtime.sh
#
# The Python version is fixed on purpose: every machine gets the same
# interpreter the preset was tested with. Change it here, not per install.
#
# Result (committed nowhere; runtime/ is gitignored):
#   runtime/<os>-<arch>/python/   unpacked python-build-standalone
#   runtime/bin/python            stable entry point used by the other skills
#                                 (python.bat on Windows, sh wrapper elsewhere)
set -euo pipefail

PY_VERSION=3.12.14
PBS_TAG=20260901   # astral-sh/python-build-standalone release tag
ROOT="$(cd "$(dirname "$0")/.." && pwd)"   # this skill's own directory

# Build in isolation from the build machine's own Python setup. Without this,
# the interpreter sees the user site-packages (~/.local/...), pip treats
# packages found there as "already satisfied", and they silently end up
# missing from the runtime that gets shipped to other machines.
export PYTHONNOUSERSITE=1 PIP_USER=0 PIP_REQUIRE_VIRTUALENV=0
unset PYTHONPATH PYTHONHOME PIP_TARGET PIP_PREFIX PIP_ROOT

case "$(uname -s)" in
    Linux)                 OS=linux ;;
    Darwin)                OS=mac ;;
    MINGW*|MSYS*|CYGWIN*)  OS=win ;;   # Windows via git-bash / MSYS2 / Cygwin
    *)                     echo "unsupported OS: $(uname -s)" >&2; exit 1 ;;
esac
case "$(uname -m)" in
    x86_64|amd64) ARCH=x64 ;;
    arm64|aarch64) ARCH=arm64 ;;
    *)             echo "unsupported arch: $(uname -m)" >&2; exit 1 ;;
esac
case "$OS-$ARCH" in
    linux-x64)   TRIPLE=x86_64-unknown-linux-gnu ;;
    linux-arm64) TRIPLE=aarch64-unknown-linux-gnu ;;
    mac-x64)     TRIPLE=x86_64-apple-darwin ;;
    mac-arm64)   TRIPLE=aarch64-apple-darwin ;;
    win-x64)     TRIPLE=x86_64-pc-windows-msvc ;;
    win-arm64)   TRIPLE=aarch64-pc-windows-msvc ;;
    *)           echo "unsupported platform: $OS-$ARCH" >&2; exit 1 ;;
esac

# From Windows PowerShell, a bare `bash` can resolve to WSL's bash.exe, which
# reports Linux and would build a Linux runtime into the Windows skills
# directory. Refuse that case: a Windows runtime must be built with git-bash.
if [ "$OS" = "linux" ] && grep -qi microsoft /proc/version 2>/dev/null; then
    case "$ROOT" in
        /mnt/[a-z]/*)
            echo "WSL bash detected on a Windows drive ($ROOT)." >&2
            echo "Run this script with git-bash to build the Windows runtime." >&2
            echo "(If OpenCode itself runs inside WSL, keep the skills on the Linux file system.)" >&2
            exit 1 ;;
    esac
fi

# Interpreter flags baked into every entry point:
#   -s       ignore the user site-packages (~/.local, %APPDATA%\Python) so the
#            customer's own packages never shadow the pinned ones
#   -E       ignore PYTHONPATH / PYTHONHOME and other PYTHON* variables
#   -X utf8  UTF-8 for files and stdio regardless of the OS locale
#            (Windows defaults to cp932 / cp1252 otherwise)
PYFLAGS="-s -E -X utf8"
IMPORTS="import pypdf, reportlab, pdfplumber, pypdfium2, openpyxl, docx, pptx, yaml"

DEST="$ROOT/runtime/$OS-$ARCH"
BUILD="$ROOT/runtime/.build-$OS-$ARCH"
ASSET="cpython-${PY_VERSION}+${PBS_TAG}-${TRIPLE}-install_only.tar.gz"
if [ "$OS" = "linux" ] || [ "$OS" = "mac" ]; then
    PYREL=python/bin/python3
else
    PYREL=python/python.exe
fi
echo "==> provisioning $OS-$ARCH Python $PY_VERSION (python-build-standalone $PBS_TAG)"

# Build next to the current runtime and swap it in only after it verifies, so
# a failed download or install (offline, proxy, interrupted) leaves an
# existing runtime untouched. Once the swap has started, a failure removes
# the entry points: runtime/bin/python must never point at a broken runtime.
ok=0
swapped=0
cleanup() {
    rm -rf "$BUILD"
    if [ "$swapped" = 1 ] && [ "$ok" != 1 ]; then
        rm -rf "$ROOT/runtime/bin"
    fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM HUP

rm -rf "$BUILD"
mkdir -p "$BUILD"
# The archive contains a top-level python/ directory; keep it so the result is
# runtime/<os>-<arch>/python/...
curl -fL --retry 3 \
    "https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_TAG}/${ASSET}" \
    | tar -xz -C "$BUILD"

# Bake the pinned dependencies into the new runtime and verify it before the
# swap: every pinned package must import from the runtime alone, and the
# dependency tree must be consistent.
"$BUILD/$PYREL" -s -m pip install --no-warn-script-location --upgrade pip
"$BUILD/$PYREL" -s -m pip install --no-warn-script-location -r "$ROOT/requirements.txt"
# shellcheck disable=SC2086  # PYFLAGS is a list of flags
"$BUILD/$PYREL" $PYFLAGS -m pip check
# shellcheck disable=SC2086
"$BUILD/$PYREL" $PYFLAGS -c "$IMPORTS"

swapped=1
rm -rf "$DEST" "$ROOT/runtime/bin"
mv "$BUILD" "$DEST"

# Stable entry point for the other skills: runtime/bin/python (all platforms,
# so SKILL.md commands are OS-independent). On Windows also write
# python.bat for cmd.exe / PowerShell.
mkdir -p "$ROOT/runtime/bin"
if [ "$OS" = "linux" ] || [ "$OS" = "mac" ]; then
    cat > "$ROOT/runtime/bin/python" <<EOF
#!/usr/bin/env sh
exec "\$(dirname "\$0")/../$OS-$ARCH/python/bin/python3" $PYFLAGS "\$@"
EOF
    chmod +x "$ROOT/runtime/bin/python"
else
    # Windows: sh wrapper for git-bash, plus python.bat for PowerShell / cmd.exe
    # (OpenCode's default shell on Windows).
    cat > "$ROOT/runtime/bin/python" <<EOF
#!/usr/bin/env sh
exec "\$(dirname "\$0")/../$OS-$ARCH/python/python.exe" $PYFLAGS "\$@"
EOF
    chmod +x "$ROOT/runtime/bin/python"
    cat > "$ROOT/runtime/bin/python.bat" <<EOF
@echo off
"%~dp0..\\$OS-$ARCH\\python\\python.exe" $PYFLAGS %*
EOF
fi
echo "==> wrote runtime/bin/python (and python.bat on Windows)"

# Verify once more through the entry point itself, after the move.
"$ROOT/runtime/bin/python" -m pip check
"$ROOT/runtime/bin/python" -c "$IMPORTS"
ok=1
echo "==> verified: all pinned packages import from the runtime"

echo "==> done: $DEST"
echo "    Other skills invoke <their skill dir>/../vega-runtime/runtime/bin/python"
