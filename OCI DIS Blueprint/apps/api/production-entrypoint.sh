#!/bin/sh
# Prepare production-only writable state and drop privileges before execution.

set -eu

if [ "$(id -u)" -eq 0 ]; then
    runtime_codex_dir="${CODEX_RUNTIME_DIR:-${HOME}/codex}"
    mkdir -p /app/uploads "$runtime_codex_dir"
    chown app:app /app/uploads "$HOME" "$runtime_codex_dir"
    chmod 0770 /app/uploads
    chmod 0700 "$HOME" "$runtime_codex_dir"

    if [ -r /codex-host/config.toml ]; then
        cp /codex-host/config.toml "$runtime_codex_dir/config.toml"
        chown app:app "$runtime_codex_dir/config.toml"
        chmod 0400 "$runtime_codex_dir/config.toml"
    fi
    if [ -r /codex-host/auth.json ]; then
        cp /codex-host/auth.json "$runtime_codex_dir/auth.json"
        chown app:app "$runtime_codex_dir/auth.json"
        chmod 0400 "$runtime_codex_dir/auth.json"
    fi

    exec su-exec app "$@"
fi

exec "$@"
