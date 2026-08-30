#!/usr/bin/env bash
set -e

echo "📦 Syncing codebase & data to Modal Volume 'llama33-repo'..."
modal volume put -f llama33-repo training /
modal volume put -f llama33-repo eval /
modal volume put -f llama33-repo data_prep /
modal volume put -f llama33-repo data /
echo "✅ Done! Volume 'llama33-repo' is up to date."
