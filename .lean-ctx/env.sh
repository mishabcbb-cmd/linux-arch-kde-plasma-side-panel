# lean-ctx: passthrough stubs for non-interactive subshells (fixes #255).
# These ensure _lc/_lc_compress exist so inherited aliases don't break.
# The full hook definitions override these when the interactive shell loads.
_lc()          { command "$@"; }
_lc_compress() { command "$@"; }

# lean-ctx shell hook — smart shell mode (track-by-default)
_lean_ctx_cmds=(git gh cargo npm pnpm yarn bun bunx deno vite pip pip3 pytest mypy ruff go golangci-lint docker docker-compose kubectl helm aws terraform tofu eslint prettier tsc biome curl wget php composer dotnet bundle rake mix swift zig cmake make rg cat head tail ls find)

_lc_is_agent() {
    [ -n "${LEAN_CTX_AGENT:-}" ] || [ -n "${CODEX_CLI_SESSION:-}" ] || [ -n "${CLAUDECODE:-}" ] || [ -n "${GEMINI_SESSION:-}" ]
}

_lc() {
    if [ -n "${LEAN_CTX_DISABLED:-}" ] || [ -n "${LEAN_CTX_NO_HOOK:-}" ]; then
        command "$@"
        return
    fi
    if [ ! -t 1 ] && ! _lc_is_agent; then
        command "$@"
        return
    fi
    '/usr/bin/lean-ctx' -t "$@"
    local _lc_rc=$?
    if [ "$_lc_rc" -eq 127 ] || [ "$_lc_rc" -eq 126 ]; then
        command "$@"
    else
        return "$_lc_rc"
    fi
}

_lc_compress() {
    if [ -n "${LEAN_CTX_DISABLED:-}" ] || [ -n "${LEAN_CTX_NO_HOOK:-}" ]; then
        command "$@"
        return
    fi
    if [ ! -t 1 ] && ! _lc_is_agent; then
        command "$@"
        return
    fi
    '/usr/bin/lean-ctx' -c "$@"
    local _lc_rc=$?
    if [ "$_lc_rc" -eq 127 ] || [ "$_lc_rc" -eq 126 ]; then
        command "$@"
    else
        return "$_lc_rc"
    fi
}

lean-ctx-on() {
    for _lc_cmd in "${_lean_ctx_cmds[@]}"; do
        # shellcheck disable=SC2139
        alias "$_lc_cmd"='_lc '"$_lc_cmd"
    done
    alias k='_lc kubectl'
    export LEAN_CTX_ENABLED=1
    [ -t 1 ] && echo "lean-ctx: ON (track mode — output unchanged, token savings recorded)"
}

lean-ctx-off() {
    for _lc_cmd in "${_lean_ctx_cmds[@]}"; do
        unalias "$_lc_cmd" 2>/dev/null || true
    done
    unalias k 2>/dev/null || true
    export LEAN_CTX_ENABLED=0
    [ -t 1 ] && echo "lean-ctx: OFF"
}

lean-ctx-mode() {
    case "${1:-}" in
        compress)
            for _lc_cmd in "${_lean_ctx_cmds[@]}"; do
                # shellcheck disable=SC2139
                alias "$_lc_cmd"='_lc_compress '"$_lc_cmd"
            done
            alias k='_lc_compress kubectl'
            export LEAN_CTX_ENABLED=1
            [ -t 1 ] && echo "lean-ctx: COMPRESS mode (all output compressed)"
            ;;
        track)
            lean-ctx-on
            ;;
        off)
            lean-ctx-off
            ;;
        *)
            echo "Usage: lean-ctx-mode <track|compress|off>"
            echo "  track    — Full output, stats recorded (default)"
            echo "  compress — Compressed output for all commands"
            echo "  off      — No aliases, raw shell"
            ;;
    esac
}

lean-ctx-raw() {
    LEAN_CTX_RAW=1 command "$@"
}

lean-ctx-status() {
    if [ -n "${LEAN_CTX_DISABLED:-}" ]; then
        [ -t 1 ] && echo "lean-ctx: DISABLED (LEAN_CTX_DISABLED is set)"
    elif [ -n "${LEAN_CTX_ENABLED:-}" ]; then
        [ -t 1 ] && echo "lean-ctx: ON"
    else
        [ -t 1 ] && echo "lean-ctx: OFF"
    fi
}

if [ -n "${ZSH_VERSION:-}" ]; then
    _lean_ctx_comp() {
        shift words
        (( CURRENT-- ))
        _normal
    }
    compdef _lean_ctx_comp _lc 2>/dev/null
    compdef _lean_ctx_comp _lc_compress 2>/dev/null
fi

_lean_ctx_should_activate() {
    [ -z "${LEAN_CTX_ACTIVE:-}" ] && [ -z "${LEAN_CTX_DISABLED:-}" ] && [ "${LEAN_CTX_ENABLED:-1}" != "0" ] || return 1
    case "${LEAN_CTX_SHELL_ACTIVATION:-always}" in
        off|none|manual) return 1 ;;
        agents-only|agents_only|agentsonly)
            [ -n "${LEAN_CTX_AGENT:-}" ] || [ -n "${CLAUDECODE:-}" ] || [ -n "${CODEX_CLI_SESSION:-}" ] || [ -n "${GEMINI_SESSION:-}" ] ;;
        *) return 0 ;;
    esac
}

if _lean_ctx_should_activate; then
    command -v lean-ctx >/dev/null 2>&1 && lean-ctx-on
fi


# lean-ctx docker self-heal: re-inject Claude MCP config if Claude overwrote ~/.claude.json
# Guards: container-only + no recursion + no re-entry via BASH_ENV + 60s cooldown + PID-lock
if [ -f /.dockerenv ] || grep -qsE '/docker/|/lxc/' /proc/1/cgroup 2>/dev/null; then
  if [ -z "${LEAN_CTX_ACTIVE:-}" ] && [ -z "${_LEAN_CTX_HEAL:-}" ]; then
    _LEAN_CTX_HEAL_TS="${HOME}/.lean-ctx/.heal_ts"
    _LEAN_CTX_HEAL_COOLDOWN=60
    _lean_ctx_heal_needed=1
    if [ -f "$_LEAN_CTX_HEAL_TS" ]; then
      _last_heal=$(cat "$_LEAN_CTX_HEAL_TS" 2>/dev/null || echo 0)
      _now=$(date +%s 2>/dev/null || echo 0)
      if [ $(( _now - _last_heal )) -lt $_LEAN_CTX_HEAL_COOLDOWN ]; then
        _lean_ctx_heal_needed=0
      fi
    fi
    _lean_ctx_lock_count=0
    for _lf in "${HOME}/.lean-ctx/locks"/slot-*.lock; do
      [ -f "$_lf" ] && _lean_ctx_lock_count=$(( _lean_ctx_lock_count + 1 ))
    done
    if [ "$_lean_ctx_heal_needed" = "1" ] && [ "$_lean_ctx_lock_count" -lt 4 ]; then
      export _LEAN_CTX_HEAL=1
      if command -v claude >/dev/null 2>&1 && command -v lean-ctx >/dev/null 2>&1; then
        if ! claude mcp list 2>/dev/null | grep -q "lean-ctx"; then
          LEAN_CTX_ACTIVE=1 LEAN_CTX_QUIET=1 lean-ctx init --agent claude >/dev/null 2>&1
          date +%s > "$_LEAN_CTX_HEAL_TS" 2>/dev/null
        fi
      fi
    fi
  fi
fi
