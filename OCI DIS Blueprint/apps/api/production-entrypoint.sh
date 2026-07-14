#!/bin/sh
# Prepare production-only writable state and drop privileges before execution.

set -eu

if [ "$(id -u)" -eq 0 ]; then
    runtime_genai_dir="${OCI_GENAI_RUNTIME_DIR:-${HOME}/.oci-genai}"
    mkdir -p /app/uploads "$runtime_genai_dir"
    chown app:app /app/uploads "$HOME" "$runtime_genai_dir"
    chmod 0770 /app/uploads
    chmod 0700 "$HOME" "$runtime_genai_dir"

    # Docker Compose may materialize a missing optional bind source as a
    # directory. Only copy a regular key file so deterministic fallback can
    # still start when OCI Generative AI credentials are intentionally absent.
    if [ -f /oci-genai-host/api_key ] && [ -r /oci-genai-host/api_key ]; then
        cp /oci-genai-host/api_key "$runtime_genai_dir/api_key"
        chown app:app "$runtime_genai_dir/api_key"
        chmod 0400 "$runtime_genai_dir/api_key"
    fi

    exec su-exec app "$@"
fi

exec "$@"
