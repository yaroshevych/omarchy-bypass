from pathlib import Path
import shutil
import subprocess
import unittest


class ServiceRecoveryTest(unittest.TestCase):
    def test_exit_restart_and_stale_approval(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        panel = (Path(__file__).resolve().parents[1] / "Panel.qml").read_text()
        functions = panel[panel.index("  function handle("):panel.index("  function openItem(")]
        review = panel[panel.index("  function reviewRequest("):panel.index("  function decideRequest(")]
        script = r'''let screen = "approval", serviceReady = true, restartVaultPath = "", vaultPath = "";
let requests = ["1"], requestId = "1", review = {targets:["secret"]}, previousScreen = "fields";
let items = [1], fields = [1], itemQueries = [1], openSearchGeneration = 1;
let itemId = "id", itemTitle = "title", itemGroup = "group", focusSearchOnResults = true;
let errorText = "old", approvalError = "old", decisionError = "old", recent = ["/vault"];
let opened = false, openedCount = 0;
const service = {running: false}, strings = {t: x => x};
const panel = {loadedContent: {passwordField: {text: "secret"}}};
const searchTimer = {stop() {}}, revealTimer = {stop() {}};
const root = {open() { openedCount++; }, reviewRequest(id) { reviewRequest(id); }};
function clearReveal() {}
function send() {}
''' + functions + review + r'''
serviceExited();
if (screen !== "recent" || errorText || serviceReady || requests.length || requestId || Object.keys(review).length || items.length || fields.length || panel.loadedContent.passwordField.text)
  throw Error("service exit retained stale state");
handle(JSON.stringify({action:"show-request", id:"1"}));
reviewRequest("1");
if (screen !== "recent" || openedCount) throw Error("stale approval opened");
openVault("/vault");
if (!service.running || screen !== "checking" || restartVaultPath !== "/vault") throw Error("restart not requested");
handle(JSON.stringify({action:"recent", recent:["/vault"]}));
if (screen !== "password" || vaultPath !== "/vault" || !serviceReady || restartVaultPath) throw Error("unlock did not resume");
service.running = false; serviceExited();
openVault("/vault"); service.running = false; serviceExited();
if (screen !== "failed" || errorText !== "service.incompatible" || restartVaultPath) throw Error("restart failure not shown");
'''
        result = subprocess.run([node, "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
