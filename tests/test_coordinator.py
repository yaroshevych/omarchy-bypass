import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class CoordinatorTest(unittest.TestCase):
    def test_only_one_owner_and_handover(self):
        qml = shutil.which("qml") or "/usr/lib/qt6/bin/qml"
        if not Path(qml).is_file():
            self.skipTest("Qt QML runner is not installed")
        plugin = Path(__file__).resolve().parents[1].as_uri()
        fixture = '''import QtQuick
import "%s" as Plugin
QtObject {
  property var first: QtObject {}
  property var second: QtObject {}
  Component.onCompleted: {
    Plugin.WidgetCoordinator.attach(first)
    Plugin.WidgetCoordinator.attach(first)
    Plugin.WidgetCoordinator.attach(second)
    if (Plugin.WidgetCoordinator.owner !== first || Plugin.WidgetCoordinator.widgets.length !== 2)
      throw new Error("first widget must remain the only owner")
    Plugin.WidgetCoordinator.detach(first)
    if (Plugin.WidgetCoordinator.owner !== second) throw new Error("handover failed")
    Plugin.WidgetCoordinator.detach(second)
    if (Plugin.WidgetCoordinator.owner !== null) throw new Error("owner not cleared")
    console.log("coordinator passed")
    Qt.quit()
  }
}
''' % plugin
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "coordinator.qml"
            path.write_text(fixture)
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="",
                       QT_STYLE_OVERRIDE="Fusion", QT_FORCE_STDERR_LOGGING="1")
            result = subprocess.run([qml, "-f", str(path)], env=env,
                                    capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("coordinator passed", result.stderr)


if __name__ == "__main__":
    unittest.main()
