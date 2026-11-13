#!/bin/zsh
set -euo pipefail
MAC_DIR="${0:A:h:h}"
PROJECT_DIR="${MAC_DIR:h:h}"
cd "$PROJECT_DIR"
if [[ $(uname -s) != Darwin ]]; then
  echo '请在 macOS 上构建。' >&2
  exit 1
fi
ARCH=$(uname -m)
if [[ "$ARCH" != arm64 && "$ARCH" != x86_64 ]]; then
  echo "不支持的架构：$ARCH" >&2
  exit 1
fi
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$HOME/Library/Caches/cc_chat/venv}"
export PYTHONDONTWRITEBYTECODE=1
BUILD_DIR=$(mktemp -d "${TMPDIR:-/tmp}/cc_chat-build.XXXXXX")
trap 'rm -rf "$BUILD_DIR"' EXIT
uv sync --frozen --group desktop --group dev
uv run --frozen --group desktop python "$MAC_DIR/scripts/prepare_macos.py"
uv run --frozen --group desktop pytest -q -p no:cacheprovider
uv run --frozen --group desktop ruff check --no-cache src tests examples "$MAC_DIR/src" "$MAC_DIR/scripts" "$MAC_DIR/packaging/desktop_entry.py"
uv run --frozen --group desktop pyinstaller --noconfirm --clean \
  --workpath "$BUILD_DIR/work" --distpath "$BUILD_DIR/dist" "$MAC_DIR/packaging/CC-Ask.spec"
VERSION=$(uv run --frozen python -c 'import ccask; print(ccask.__version__)')
/usr/bin/codesign --verify --deep --strict "$BUILD_DIR/dist/CC Ask.app"
rm -rf "$MAC_DIR/CC Ask.app"
/usr/bin/ditto "$BUILD_DIR/dist/CC Ask.app" "$MAC_DIR/CC Ask.app"
/usr/bin/ditto -c -k --sequesterRsrc --keepParent "$MAC_DIR/CC Ask.app" "$MAC_DIR/CC-Ask-${VERSION}-macos-${ARCH}.zip"
echo "构建完成：$MAC_DIR/CC-Ask-${VERSION}-macos-${ARCH}.zip"
