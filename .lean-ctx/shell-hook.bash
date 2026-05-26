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
