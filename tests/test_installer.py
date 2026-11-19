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
            "x86_64": "4cbd956a501f520a0dad297fecad626e47089b419bd3fcb5f951398d86f51615",
            "aarch64": "858dd72b3d796e249c3238ad0da5039a27a762f9c1b882f558306fe49b3006f0",
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
