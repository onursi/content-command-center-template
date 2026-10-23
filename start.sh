#!/bin/sh
# Startet das Board im Hintergrund. Adresse: http://127.0.0.1:8899
cd "$(dirname "$0")"
nohup python3 server.py >/dev/null 2>&1 &
echo "Content Command Center gestartet (PID $!)"
