#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Installing Python dependencies (rich)"
python3 -m pip install --user -q -r "$SCRIPT_DIR/requirements.txt"

echo "==> Making bin/claude-usage executable"
chmod +x "$SCRIPT_DIR/bin/claude-usage"

echo "==> Linking claude-usage onto your PATH"
mkdir -p "$HOME/.local/bin"
ln -sf "$SCRIPT_DIR/bin/claude-usage" "$HOME/.local/bin/claude-usage"

case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *)
    echo ""
    echo "NOTE: $HOME/.local/bin is not on your PATH."
    echo "Add this to your shell profile (~/.zshrc or ~/.bashrc):"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    ;;
esac

echo "==> Wiring the statusLine hook into ~/.claude/settings.json"
python3 - "$SCRIPT_DIR" <<'PYEOF'
import json
import os
import sys

script_dir = sys.argv[1]
settings_path = os.path.expanduser("~/.claude/settings.json")
statusline_path = os.path.join(script_dir, "usage_statusline.py")

settings = {}
if os.path.exists(settings_path):
    with open(settings_path) as f:
        settings = json.load(f)

settings["statusLine"] = {
    "type": "command",
    "command": "python3 {}".format(statusline_path),
}

os.makedirs(os.path.dirname(settings_path), exist_ok=True)
with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")

print("Updated {} (statusLine only, other settings preserved)".format(settings_path))
PYEOF

echo ""
echo "==> Done. Send at least one message in any Claude Code session so it"
echo "    reports usage data, then run:"
echo ""
echo "      claude-usage"
echo ""
