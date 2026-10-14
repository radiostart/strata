#!/bin/sh
# strata hook launcher: run.sh <hook-name>
#
# Finds Python 3.11+ and runs scripts/hook.py with the payload on stdin.
# Without a usable Python:
#   - a project with no .strata/strata.toml is untouched (exit 0);
#   - otherwise file-writing tools are blocked (exit 2) and Bash gets a warning (exit 1), because a
#     Bash command cannot be judged without Python and blocking every command would lock the way out.

hook="$1"
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
root="${CLAUDE_PLUGIN_ROOT:-$(dirname -- "$here")}"

for py in python3 python3.14 python3.13 python3.12 python3.11 python; do
  if command -v "$py" >/dev/null 2>&1 \
    && "$py" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' </dev/null >/dev/null 2>&1; then
    exec "$py" "$root/scripts/hook.py" "$hook"
  fi
done

project="${CLAUDE_PROJECT_DIR:-$PWD}"
[ -f "$project/.strata/strata.toml" ] || exit 0
[ "${STRATA_GUARD_BYPASS:-}" = "1" ] && exit 0

payload=$(cat)
msg="strata: Python 3.11 or later is required to check writes in this project and none was found. Install it, or restart Claude Code with STRATA_GUARD_BYPASS=1 if this is approved."
case "$payload" in
  *'"tool_name":"Bash"'*|*'"tool_name": "Bash"'*)
    echo "$msg (Bash commands are not being checked.)" >&2
    exit 1
    ;;
esac
echo "$msg" >&2
exit 2
