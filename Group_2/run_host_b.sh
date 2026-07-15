#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")"
python3 host_b.py
echo
echo "[host_b.py exited - press Ctrl-D or close this window]"
exec bash
