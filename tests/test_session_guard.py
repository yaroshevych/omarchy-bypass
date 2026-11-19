import importlib.util
import os
from pathlib import Path
import socket
import shutil
import subprocess
import tempfile
import unittest


spec = importlib.util.spec_from_file_location('session_guard', Path(__file__).resolve().parents[1] / 'check-running-bypass.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class SessionGuardTest(unittest.TestCase):
    def test_old_tui_is_blocked_but_current_and_short_commands_are_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current = root / 'current'
            old = root / 'old'
            current.write_bytes(b'current')
            old.write_bytes(b'old')
            proc = root / 'proc'
            proc.mkdir()
            process = proc / '123'
            process.mkdir()
            (process / 'comm').write_text('bypass\n')
            (process / 'cmdline').write_bytes(b'/home/user/bypass\0vault.kdbx\0')
            (process / 'exe').symlink_to(current)
            expected = current.stat()
            guard.check_processes(proc, expected, os.getuid())
            (process / 'exe').unlink()
            (process / 'exe').symlink_to(old)
            with self.assertRaises(guard.UnsafeSession):
                guard.check_processes(proc, expected, os.getuid())
            (process / 'cmdline').write_bytes(b'/home/user/bypass\0run\0--\0true\0')
            guard.check_processes(proc, expected, os.getuid())
            (process / 'cmdline').write_bytes(b'/home/user/bypass\0vault.kdbx\0')
            (process / 'exe').unlink()
            with self.assertRaises(guard.UnsafeSession):
                guard.check_processes(proc, expected, os.getuid())
            (process / 'cmdline').write_bytes(b'')
            guard.check_processes(proc, expected, os.getuid())

    def test_replaced_executable_is_detected_while_process_runs(self):
        sleep = shutil.which('sleep')
        if not sleep:
            self.skipTest('sleep is unavailable')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / 'bypass'
            shutil.copy(sleep, binary)
            process = subprocess.Popen([str(binary), '20'])
            try:
                fake_proc = root / 'proc'
                fake_proc.mkdir()
                fake_process = fake_proc / str(process.pid)
                fake_process.mkdir()
                for name in ('comm', 'cmdline', 'exe'):
                    (fake_process / name).symlink_to(Path('/proc') / str(process.pid) / name)
                guard.check_processes(fake_proc, binary.stat(), os.getuid())
                replacement = root / 'replacement'
                shutil.copy(sleep, replacement)
                os.replace(replacement, binary)
                with self.assertRaises(guard.UnsafeSession):
                    guard.check_processes(fake_proc, binary.stat(), os.getuid())
            finally:
                process.terminate()
                process.wait(timeout=5)

    def test_socket_checks_actual_peer_even_when_executable_is_renamed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'run.sock'
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                listener.bind(str(path))
                listener.listen(4)
                guard.check_socket(path, os.stat('/proc/self/exe'), os.getuid())
                other = Path(directory) / 'other'
                other.write_bytes(b'different')
                with self.assertRaises(guard.UnsafeSession):
                    guard.check_socket(path, other.stat(), os.getuid())
            finally:
                listener.close()
            guard.check_socket(path, os.stat('/proc/self/exe'), os.getuid())

    def test_launcher_refuses_to_focus_when_guard_fails(self):
        plugin = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mock_bin = root / 'bin'
            mock_bin.mkdir()
            python = mock_bin / 'python3'
            python.write_text('#!/bin/sh\nexit 42\n')
            python.chmod(0o755)
            hyprctl = mock_bin / 'hyprctl'
            hyprctl.write_text('#!/bin/sh\ntouch "$TEST_MARKER"\n')
            hyprctl.chmod(0o755)
            env = dict(os.environ, PATH=str(mock_bin) + os.pathsep + os.environ['PATH'], TEST_MARKER=str(root / 'called'))
            result = subprocess.run(['sh', str(plugin / 'launch-edit.sh'), '/bin/true'], env=env)
            self.assertEqual(result.returncode, 42)
            self.assertFalse((root / 'called').exists())

    def test_discovers_sockets_from_other_cache_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            uid = os.getuid()
            paths = [root / f'bypass-{uid}-0123456789abcdef', root / f'bypass-{uid}-fedcba9876543210']
            for path in paths:
                path.mkdir()
            (root / f'bypass-{uid}-not-a-hash').mkdir()
            found = set(guard.socket_paths(uid, root))
            self.assertEqual(found, {path / 'run.sock' for path in paths})

    def test_cache_path_matches_bypass_socket_naming(self):
        previous = os.environ.get('XDG_CACHE_HOME')
        try:
            os.environ['XDG_CACHE_HOME'] = '/tmp/test-cache'
            path = guard.run_socket_path()
            self.assertEqual(path.name, 'run.sock')
            self.assertEqual(path.parent.name, f'bypass-{os.getuid()}-74e2752023d67fe0')
            os.environ['XDG_CACHE_HOME'] = 'relative'
            with self.assertRaises(guard.UnsafeSession):
                guard.run_socket_path()
        finally:
            if previous is None:
                os.environ.pop('XDG_CACHE_HOME', None)
            else:
                os.environ['XDG_CACHE_HOME'] = previous


if __name__ == '__main__':
    unittest.main()
