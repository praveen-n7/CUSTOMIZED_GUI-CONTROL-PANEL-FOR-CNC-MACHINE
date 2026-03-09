#!/usr/bin/env python3
"""Shared helper: write one command to the handler FIFO."""
import os, sys, errno

FIFO = '/tmp/linuxcnc_mcode.fifo'

def send(cmd):
    if not os.path.exists(FIFO):
        print(f"[mcode] FIFO missing — panel not running?", file=sys.stderr)
        sys.exit(0)
    try:
        fd = os.open(FIFO, os.O_WRONLY | os.O_NONBLOCK)
        os.write(fd, (cmd.strip() + '\n').encode())
        os.close(fd)
        print(f"[mcode] → {cmd.strip()}")
    except OSError as e:
        if e.errno not in (errno.ENXIO, errno.EAGAIN):
            print(f"[mcode] write error: {e}", file=sys.stderr)
    sys.exit(0)
