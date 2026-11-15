import json
from pathlib import Path
import shutil
import subprocess
import unittest


class SearchTest(unittest.TestCase):
    def test_enter_waits_for_latest_search(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        panel = (Path(__file__).resolve().parents[1] / "Panel.qml").read_text()
        handle = panel[panel.index("  function handle("):panel.index("  function displayPath(")]
        search = panel[panel.index("  function searchItems("):panel.index("  Timer { id: searchTimer")]
        script = r'''let items = [], itemQueries = [], searchGeneration = 0, openSearchGeneration = -1;
let screen = "items", errorText = "", focusSearchOnResults = false, stoppingService = false;
let openedItem = null, sent = [];
const service = {running: true}, strings = {t: x => x};
const panel = {loadedContent: {queryField: {text: "old"}}};
const searchTimer = {stop() {}};
function send(value) { sent.push(value); }
function openItem(item) { openedItem = item; }
''' + handle + search + r'''searchItems("old");
searchGeneration++;
panel.loadedContent.queryField.text = "new";
acceptSearch();
handle(JSON.stringify({action:"items", items:[{Title:"old"}]}));
if (openedItem || items.length) throw Error("stale result accepted");
handle(JSON.stringify({action:"items", items:[{Title:"new"}]}));
if (!openedItem || openedItem.Title !== "new") throw Error("latest result not opened");
openedItem = null; screen = "items"; searchGeneration++;
searchItems("failure");
handle(JSON.stringify({action:"items", error:"failed"}));
searchGeneration++; acceptSearch();
handle(JSON.stringify({action:"items", items:[{Title:"after error"}]}));
if (!openedItem || openedItem.Title !== "after error") throw Error("error disrupted response queue");
'''
        result = subprocess.run([node, "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
