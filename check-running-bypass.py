#!/usr/bin/env python3
"""Refuse widget use while an older Bypass session may still hold grants."""
import errno
import hashlib
import os
import re
from pathlib import Path
import socket
import stat
import struct
import sys


class UnsafeSession(Exception):
    pass


def same_executable(path, expected):
    actual = os.stat(path)
    return (actual.st_dev, actual.st_ino) == (expected.st_dev, expected.st_ino)


def check_socket(path, expected, uid, proc_root=Path('/proc')):
    # Bypass only creates IPC servers in real directories owned by this user.
    # Other users can create matching names in /tmp, but cannot host our server.
    try:
        directory = path.parent.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise UnsafeSession from exc
    if directory.st_uid != uid:
        return
    if not stat.S_ISDIR(directory.st_mode):
        raise UnsafeSession
    # SO_PEERCRED identifies the actual server, including a renamed executable.
    conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    conn.settimeout(0.5)
    try:
        try:
            conn.connect(str(path))
        except OSError as exc:
            if exc.errno in (errno.ENOENT, errno.ECONNREFUSED):
                return
            raise UnsafeSession from exc
        pid, peer_uid, _ = struct.unpack('3i', conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('3i')))
        if peer_uid != uid or not same_executable(proc_root / str(pid) / 'exe', expected):
            raise UnsafeSession
    except OSError as exc:
        raise UnsafeSession from exc
    finally:
        conn.close()


def check_processes(proc_root, expected, uid):
    try:
        entries = list(proc_root.iterdir())
    except OSError as exc:
        raise UnsafeSession from exc
    for process in entries:
        if not process.name.isdigit():
            continue
        try:
            if process.stat().st_uid != uid:
                continue
            comm = (process / 'comm').read_text().strip()
            if not comm.startswith('bypass'):
                continue
            args = (process / 'cmdline').read_bytes().split(b'\0')
            if not args[0]:  # A zombie cannot retain a live session.
                continue
            # These short-lived commands cannot hold TUI session approvals.
            if len(args) > 1 and args[1] in (b'run', b'widget-recent', b'help', b'--help', b'--version'):
                continue
            if not same_executable(process / 'exe', expected):
                raise UnsafeSession
        except FileNotFoundError:
            if process.exists():
                raise UnsafeSession
            continue
        except (OSError, UnicodeError) as exc:
            raise UnsafeSession from exc


def run_socket_path():
    cache = os.environ.get('XDG_CACHE_HOME')
    if cache:
        if not os.path.isabs(cache):
            raise UnsafeSession
    else:
        home = os.environ.get('HOME')
        if not home:
            raise UnsafeSession
        cache = home + '/.cache'
    digest = hashlib.sha256(os.fsencode(cache)).hexdigest()[:16]
    return Path('/tmp') / f'bypass-{os.getuid()}-{digest}' / 'run.sock'


def socket_paths(uid, tmp_root=Path('/tmp')):
    # Different TUI launches may use different XDG_CACHE_HOME values.
    pattern = re.compile(r'^bypass-' + str(uid) + r'-[0-9a-f]{16}$')
    try:
        return [entry / 'run.sock' for entry in tmp_root.iterdir() if pattern.fullmatch(entry.name)]
    except OSError as exc:
        raise UnsafeSession from exc


def main():
    if len(sys.argv) != 2:
        return 42
    try:
        expected = os.stat(sys.argv[1])
        uid = os.getuid()
        paths = set(socket_paths(uid))
        paths.add(run_socket_path())
        for path in paths:
            check_socket(path, expected, uid)
        check_processes(Path('/proc'), expected, uid)
    except (OSError, UnsafeSession):
        return 42
    return 0


if __name__ == '__main__':
    sys.exit(main())
