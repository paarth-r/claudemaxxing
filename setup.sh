#!/usr/bin/env bash
#
# claudemaxxing suite setup.
#
# Run this after cloning the repo. It installs whichever parts you want:
#
#   claudemaxxing   the 5-hour usage dashboard (statusline + TUI)
#   brain           per-project agent memory with hook-enforced rules
#
# Everything it does is reversible, and it tells you how to reverse it.
#
#   ./setup.sh              interactive: asks which parts you want
#   ./setup.sh --all        both, no questions
#   ./setup.sh --brain      brain only
#   ./setup.sh --dashboard  dashboard only
#   ./setup.sh --uninstall  remove what this script installed
#
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MARKETPLACE="claudemaxxing"
PLUGIN="brain"

bold() { printf '\033[1m%s\033[0m\n' "$1"; }
dim()  { printf '\033[2m%s\033[0m\n' "$1"; }
ok()   { printf '  \033[32mok\033[0m  %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m   %s\n' "$1"; }
die()  { printf '\033[31merror\033[0m %s\n' "$1" >&2; exit 1; }

# ---------------------------------------------------------------- preflight

preflight() {
  bold "Checking your machine"

  command -v python3 >/dev/null 2>&1 || die "python3 not found. Install Python 3.9 or newer."
  local pyver
  pyver="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
  python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' \
    || die "python3 is $pyver; brain needs 3.9 or newer."
  ok "python3 $pyver"

  if command -v claude >/dev/null 2>&1; then
    ok "claude CLI on PATH"
  else
    die "claude CLI not found. Install Claude Code first: https://claude.ai/code"
  fi
  echo
}

# ---------------------------------------------------------------- dashboard

install_dashboard() {
  bold "Installing the claudemaxxing dashboard"
  if [ ! -x "$REPO/install.sh" ]; then
    warn "install.sh not found or not executable; skipping the dashboard."
    return
  fi
  "$REPO/install.sh"
  echo
}

# ---------------------------------------------------------------- brain

install_brain() {
  bold "Installing the brain plugin"

  # Adding an already-known marketplace is not an error worth stopping for.
  if claude plugin marketplace list 2>/dev/null | grep -q "$MARKETPLACE"; then
    ok "marketplace '$MARKETPLACE' already registered"
  else
    claude plugin marketplace add "$REPO" >/dev/null
    ok "marketplace '$MARKETPLACE' added"
  fi

  if claude plugin list 2>/dev/null | grep -q "$PLUGIN@$MARKETPLACE"; then
    ok "plugin '$PLUGIN' already installed"
  else
    claude plugin install "$PLUGIN@$MARKETPLACE" >/dev/null
    ok "plugin '$PLUGIN' installed"
  fi

  local bin="$HOME/.local/bin"
  mkdir -p "$bin"
  cat > "$bin/brain" <<EOF
#!/usr/bin/env bash
exec python3 "$REPO/plugins/brain/cli.py" "\$@"
EOF
  chmod +x "$bin/brain"
  ok "brain command -> $bin/brain"

  case ":$PATH:" in
    *":$bin:"*) ;;
    *) warn "$bin is not on your PATH. Add it, or call the CLI by full path." ;;
  esac
  echo
}

# ---------------------------------------------------------------- mirror

configure_mirror() {
  local config="$HOME/.brain/config.yml"
  if [ -f "$config" ] && grep -q '^mirror:' "$config"; then
    ok "vault mirror already configured ($config)"
    echo
    return
  fi

  bold "Mirror your brains to a notes vault? (optional)"
  dim "Each project's brain can be copied to a folder you can open in Obsidian."
  dim "Leave this blank and nothing is ever written outside your repos."
  printf '  Vault folder (blank to skip): '
  read -r vault < /dev/tty || vault=""

  if [ -z "$vault" ]; then
    ok "mirroring off (the default)"
    echo
    return
  fi

  mkdir -p "$HOME/.brain"
  printf 'mirror: %s\n' "$vault" >> "$config"
  ok "mirror -> $vault"
  dim "  Applies to every repo. Change it any time in $config"
  echo
}

# ---------------------------------------------------------------- uninstall

uninstall() {
  bold "Removing what setup.sh installed"

  claude plugin uninstall "$PLUGIN@$MARKETPLACE" >/dev/null 2>&1 \
    && ok "plugin '$PLUGIN' uninstalled" \
    || warn "plugin '$PLUGIN' was not installed"

  claude plugin marketplace remove "$MARKETPLACE" >/dev/null 2>&1 \
    && ok "marketplace '$MARKETPLACE' removed" \
    || warn "marketplace '$MARKETPLACE' was not registered"

  [ -f "$HOME/.local/bin/brain" ] && rm -f "$HOME/.local/bin/brain" && ok "brain command removed"

  echo
  dim "Left alone on purpose:"
  dim "  Your .brain/ folders. The knowledge outlives the tool."
  dim "    remove with:  rm -rf <repo>/.brain"
  dim "  Your ~/.brain/config.yml and the statusLine in ~/.claude/settings.json."
  dim "    (setup.sh never rewrote settings.json; install.sh added the statusLine.)"
  echo
  bold "Restart Claude Code to unload the hooks."
}

# ---------------------------------------------------------------- main

main() {
  local want_dashboard=0 want_brain=0

  case "${1:-}" in
    --uninstall) preflight; uninstall; exit 0 ;;
    --all)       want_dashboard=1; want_brain=1 ;;
    --brain)     want_brain=1 ;;
    --dashboard) want_dashboard=1 ;;
    --help|-h)   sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    "")          ;;
    *)           die "unknown option: $1  (try --help)" ;;
  esac

  echo
  bold "claudemaxxing suite"
  dim "$REPO"
  echo

  preflight

  if [ "$want_dashboard" -eq 0 ] && [ "$want_brain" -eq 0 ]; then
    dim "Two things live here. Install either, both, or neither."
    echo
    printf '  Install the usage dashboard? [Y/n] '
    read -r answer < /dev/tty || answer="y"
    [[ "$answer" =~ ^[Nn] ]] || want_dashboard=1

    printf '  Install the brain plugin?     [Y/n] '
    read -r answer < /dev/tty || answer="y"
    [[ "$answer" =~ ^[Nn] ]] || want_brain=1
    echo
  fi

  [ "$want_dashboard" -eq 1 ] && install_dashboard
  if [ "$want_brain" -eq 1 ]; then
    install_brain
    configure_mirror
  fi

  bold "Done."
  echo

  if [ "$want_brain" -eq 1 ]; then
    bold "One more step, and it matters"
    dim "Hooks only register when Claude Code starts. Until you restart, brain does nothing."
    echo "  Restart Claude Code, then in any repo you want memory for:"
    echo
    echo "      brain init"
    echo
    dim "That mines your AGENTS.md / README for rules a hook can actually enforce."
    dim "Repos without a .brain/ are untouched: every hook exits immediately."
    echo
    bold "If it ever misbehaves"
    echo "      touch ~/.brain/DISABLED     # everything off, instantly"
    echo "      ./setup.sh --uninstall      # remove it properly"
    echo
  fi
}

main "$@"
