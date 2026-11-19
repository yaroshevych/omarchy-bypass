import hashlib
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest


class InstallerTest(unittest.TestCase):
    def test_pinned_download_and_checksum_failure(self):
        source = (Path(__file__).resolve().parents[1] / "install-bypass.sh").read_text()
        expected = {
            "x86_64": "54e72fa2b67680c7a343dc47d8a0d2448506cab676381e00cfe2587dd79ab27a",
            "aarch64": "16b2531b2fd23bc128781c76b42e38cb38fa068dcae99d35e4ae0976f3659cfe",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "fixture.tar.gz"
            payload = b"#!/bin/sh\nprintf 'fixture\\n'\n"
            with tarfile.open(archive, "w:gz") as tar:
                info = tarfile.TarInfo("bypass")
                info.size = len(payload)
                info.mode = 0o755
                tar.addfile(info, io.BytesIO(payload))
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            mock_bin = root / "bin"
            mock_bin.mkdir()
            curl = mock_bin / "curl"
            curl.write_text('''#!/bin/sh
while [ "$#" -gt 0 ]; do
  if [ "$1" = "--output" ]; then shift; out=$1; fi
  shift
done
cp "$FIXTURE_ARCHIVE" "$out"
''')
            curl.chmod(0o755)
            uname = mock_bin / "uname"
            uname.write_text('#!/bin/sh\nprintf "%s\\n" "$FIXTURE_ARCH"\n')
            uname.chmod(0o755)
            env = dict(os.environ, HOME=str(root / "home"),
                       PATH=str(mock_bin) + os.pathsep + os.environ["PATH"],
                       FIXTURE_ARCHIVE=str(archive))
            for arch, checksum in expected.items():
                with self.subTest(arch=arch):
                    env["FIXTURE_ARCH"] = arch
                    script = root / "installer.sh"
                    script.write_text(source.replace(checksum, digest))
                    result = subprocess.run(["sh", str(script)], env=env, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    installed = root / "home/.local/bin/bypass"
                    self.assertEqual(installed.read_bytes(), payload)
                    self.assertTrue(os.access(installed, os.X_OK))
                    installed.write_bytes(b"existing")
                    script.write_text(source)
                    result = subprocess.run(["sh", str(script)], env=env, capture_output=True, text=True)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(installed.read_bytes(), b"existing")


if __name__ == "__main__":
    unittest.main()
