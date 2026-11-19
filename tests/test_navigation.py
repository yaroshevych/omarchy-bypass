import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class WidgetNavigationTest(unittest.TestCase):
    def test_escape_returns_to_list_then_closes(self):
        panel = (Path(__file__).resolve().parents[1] / "Panel.qml").read_text()
        start = panel.index("  function escapeView(")
        end = panel.index("\n  function searchItems(", start)
        escape_view = panel[start:end]
        qml = '''import QtQuick
QtObject {
 property string screen: "fields"
 property var fields: ["synthetic"]
 property bool closed: false
 property string errorText: "error"
 property var panel: QtObject {
  property var loadedContent: QtObject {
   property var passwordField: QtObject { property string text: "synthetic password" }
   property var queryField: QtObject { property string text: "query" }
  }
 }
 function close() { closed = true }
 function stopService(next) { screen = next }
 function searchItems(query) {}
''' + escape_view + '''
 Component.onCompleted: {
  if (!escapeView() || screen !== "items" || fields.length !== 0 || closed) throw new Error("item escape")
  if (!escapeView() || !closed) throw new Error("list escape")
  screen = "password"; closed = false
  if (!escapeView() || screen !== "recent" || closed || panel.loadedContent.passwordField.text !== "" || errorText !== "") throw new Error("password escape")
  console.log("escape passed")
  Qt.quit()
 }
}
'''
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "escape.qml"
            fixture.write_text(qml)
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="",
                       QT_STYLE_OVERRIDE="Fusion", QT_FORCE_STDERR_LOGGING="1")
            result = subprocess.run(["/usr/lib/qt6/bin/qml", "-f", str(fixture)],
                                    env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("escape passed", result.stderr)

    def test_display_path_uses_home_and_preserves_other_paths(self):
        panel = (Path(__file__).resolve().parents[1] / "Panel.qml").read_text()
        start = panel.index("  function displayPath(")
        end = panel.index("\n  function openVault(", start)
        qml = '''import QtQuick
import QtCore
QtObject {
''' + panel[start:end] + '''
 Component.onCompleted: {
  const home = decodeURIComponent(StandardPaths.writableLocation(StandardPaths.HomeLocation).toString().replace(/^file:\/\//, ""))
  if (displayPath(home + "/vault.kdbx") !== "~/vault.kdbx") throw new Error("home path")
  if (displayPath("/other/vault.kdbx") !== "/other/vault.kdbx") throw new Error("other path")
  console.log("path passed")
  Qt.quit()
 }
}
'''
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "path.qml"
            fixture.write_text(qml)
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="",
                       QT_STYLE_OVERRIDE="Fusion", QT_FORCE_STDERR_LOGGING="1")
            result = subprocess.run(["/usr/lib/qt6/bin/qml", "-f", str(fixture)],
                                    env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("path passed", result.stderr)

    def test_password_and_item_navigation(self):
        panel = (Path(__file__).resolve().parents[1] / "Panel.qml").read_text()
        start = panel.index("  function moveList(")
        end = panel.index("\n  function reviewRequest(", start)
        move_list = panel[start:end]
        qml = '''import QtQuick
QtObject {
 id: root
 property string last: ""
 property var recent: []
 property var filteredRecent: []
 property var items: ["first", "second"]
 property var fields: ["username", "password"]
 property var panel: QtObject {
  property var loadedContent: QtObject {
   property var queryField: QtObject { function forceActiveFocus() { root.last = "search" } }
   property var showAllButton: QtObject { property bool visible: false; function forceActiveFocus() { root.last = "show-all" } }
   property var itemRepeater: QtObject {
    function itemAt(index) { return index === 0 ? first : second }
    property var first: QtObject { function forceActiveFocus() { root.last = "first-item" } }
    property var second: QtObject { function forceActiveFocus() { root.last = "second-item" } }
   }
   property var passwordField: QtObject { function forceActiveFocus() { root.last = "password" } }
   property var unlockButton: QtObject { function forceActiveFocus() { root.last = "unlock" } }
   property var passwordBackButton: QtObject { function forceActiveFocus() { root.last = "back" } }
   property var fieldsBackButton: QtObject { function forceActiveFocus() { root.last = "fields-back" } }
   property var editAction: QtObject { property bool enabled: true; property bool visible: true; function forceActiveFocus() { root.last = "edit" } }
   property var revealAction: QtObject { property bool enabled: false; property bool visible: true; function forceActiveFocus() { root.last = "reveal" } }
   property var favoriteAction: QtObject { property bool enabled: true; property bool visible: true; function forceActiveFocus() { root.last = "favorite" } }
   property var fieldRepeater: QtObject {
    function itemAt(index) { return index === 0 ? first : second }
    property var first: QtObject { function forceActiveFocus() { root.last = "username" } }
    property var second: QtObject { function forceActiveFocus() { root.last = "password-field" } }
   }
   function ensureVisible(item) {}
  }
 }
''' + move_list + '''
 Component.onCompleted: {
  moveList("items", -1, 1); if (last !== "first-item") throw new Error("search down")
  moveList("items", 0, 1); if (last !== "second-item") throw new Error("item down")
  moveList("items", 1, -1); if (last !== "first-item") throw new Error("item up")
  moveList("items", 0, -1); if (last !== "search") throw new Error("search up")
  moveList("items", 1, 1); if (last !== "search") throw new Error("hidden show all skipped")
  panel.loadedContent.showAllButton.visible = true
  moveList("items", 1, 1); if (last !== "show-all") throw new Error("visible show all")
  moveList("password", 0, 1); if (last !== "password") throw new Error("back down")
  moveList("password", 1, 1); if (last !== "unlock") throw new Error("password down")
  moveList("password", 2, -1); if (last !== "password") throw new Error("unlock up")
  moveList("password", 1, -1); if (last !== "back") throw new Error("password up")
  moveList("fields", 0, 1); if (last !== "username") throw new Error("fields first")
  moveList("fields", 1, 1); if (last !== "password-field") throw new Error("fields down")
  moveList("fields", 2, -1); if (last !== "username") throw new Error("fields up")
  moveList("fields", 1, -1); if (last !== "fields-back") throw new Error("fields back")
  moveList("fields", 2, 1); if (last !== "edit") throw new Error("fields to actions")
  moveList("fields", 3, 1); if (last !== "favorite") throw new Error("skip disabled action")
  moveList("fields", 5, -1); if (last !== "edit") throw new Error("reverse skip disabled action")
  moveList("fields", 3, -1); if (last !== "password-field") throw new Error("actions to fields")
  moveFieldAction(0, 1); if (last !== "favorite") throw new Error("right skips disabled action")
  moveFieldAction(2, -1); if (last !== "edit") throw new Error("left skips disabled action")
  panel.loadedContent.revealAction.enabled = true
  moveFieldAction(0, 1); if (last !== "reveal") throw new Error("right reaches reveal")
  console.log("navigation passed")
  Qt.quit()
 }
}
'''
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "navigation.qml"
            fixture.write_text(qml)
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="",
                       QT_STYLE_OVERRIDE="Fusion", QT_FORCE_STDERR_LOGGING="1")
            result = subprocess.run(["/usr/lib/qt6/bin/qml", "-f", str(fixture)],
                                    env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("navigation passed", result.stderr)


if __name__ == "__main__":
    unittest.main()
