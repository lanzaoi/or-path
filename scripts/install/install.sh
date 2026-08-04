#!/usr/bin/env bash
# OR-Path L2 installer (best-effort Linux/macOS)
# Usage:
#   curl -fsSL https://github.com/lanzaoi/or-path/releases/download/v0.2.0/install.sh | bash
#   ./install.sh --local-zip ./dist/orpath-0.2.0-win-x64.zip --install-dir "$HOME/orpath"
set -euo pipefail

VERSION="${ORPATH_VERSION:-latest}"
REPO="${ORPATH_REPO:-lanzaoi/or-path}"
INSTALL_DIR="${ORPATH_INSTALL_DIR:-${HOME}/.local/share/orpath}"
LOCAL_ZIP=""
SKIP_SETUP=0
PLATFORM="linux-x64"
case "$(uname -s)" in
  Darwin) PLATFORM="darwin-arm64" ;;
  Linux) PLATFORM="linux-x64" ;;
esac

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version) VERSION="$2"; shift 2 ;;
    --repo) REPO="$2"; shift 2 ;;
    --install-dir) INSTALL_DIR="$2"; shift 2 ;;
    --local-zip) LOCAL_ZIP="$2"; shift 2 ;;
    --skip-setup) SKIP_SETUP=1; shift ;;
    --platform) PLATFORM="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

resolve_latest() {
  local html
  html="$(curl -fsSL "https://github.com/${REPO}/releases/latest")"
  echo "$html" | sed -n 's/.*releases\/tag\/v\([0-9][^"'"'"'<> ]*\).*/\1/p' | head -n1
}

TMP="$(mktemp -d)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

if [[ -n "$LOCAL_ZIP" ]]; then
  ZIP="$LOCAL_ZIP"
  VER="local"
else
  if [[ "$VERSION" == "latest" || "$VERSION" == "stable" ]]; then
    VER="$(resolve_latest)"
    [[ -n "$VER" ]] || { echo "failed to resolve latest" >&2; exit 1; }
  else
    VER="${VERSION#v}"
  fi
  ASSET="orpath-${VER}-${PLATFORM}.zip"
  # fall back to win-x64 bundle name if platform-specific missing (source-heavy)
  URL="https://github.com/${REPO}/releases/download/v${VER}/${ASSET}"
  ZIP="$TMP/$ASSET"
  echo "==> Downloading $URL"
  if ! curl -fsSL "$URL" -o "$ZIP"; then
    ASSET="orpath-${VER}-win-x64.zip"
    URL="https://github.com/${REPO}/releases/download/v${VER}/${ASSET}"
    echo "==> fallback $URL"
    curl -fsSL "$URL" -o "$ZIP"
  fi
fi

echo "==> Extracting"
mkdir -p "$TMP/extract"
unzip -q "$ZIP" -d "$TMP/extract"
BUNDLE="$(find "$TMP/extract" -mindepth 1 -maxdepth 1 -type d | head -n1)"
[[ -f "$BUNDLE/orpath.sh" || -f "$BUNDLE/orpath.bat" ]] || { echo "bundle missing launcher" >&2; exit 1; }

echo "==> Installing to $INSTALL_DIR"
rm -rf "$INSTALL_DIR"
mkdir -p "$(dirname "$INSTALL_DIR")"
mv "$BUNDLE" "$INSTALL_DIR"

# If node_modules are wrong-arch, user can re-npm
if [[ ! -f "$INSTALL_DIR/runtime/node_modules/@earendil-works/pi-coding-agent/dist/cli.js" ]]; then
  echo "==> runtime Pi missing; npm ci"
  (cd "$INSTALL_DIR/runtime" && npm ci || npm install)
fi

if [[ "$SKIP_SETUP" -eq 0 ]]; then
  echo "==> setup"
  if [[ -x "$INSTALL_DIR/orpath.sh" ]]; then
    (cd "$INSTALL_DIR" && bash ./orpath.sh setup) || true
  else
    (cd "$INSTALL_DIR" && python3 scripts/bootstrap_orpath.py) || true
  fi
fi

BIN_DIR="${HOME}/.local/bin"
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/orpath" <<EOF
#!/usr/bin/env bash
exec bash "$INSTALL_DIR/orpath.sh" "\$@"
EOF
chmod +x "$BIN_DIR/orpath"

echo "PASS: installed $INSTALL_DIR"
echo "  export PATH=\"$BIN_DIR:\$PATH\""
echo "  orpath doctor"
echo "  orpath setup"
