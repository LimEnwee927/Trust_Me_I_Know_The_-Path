#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")"
python3 sender.py --iface h1-eth1 --max-packets 100
echo
echo "[sender.py exited - press Ctrl-D or close this window]"
exec bash
