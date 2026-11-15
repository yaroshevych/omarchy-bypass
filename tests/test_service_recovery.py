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
        script = r'''let screen = "approval", serviceReady = true, pendingPassword = "", vaultPath = "";
let stoppingService = false, stopScreen = "recent";
let requests = ["1"], requestId = "1", review = {targets:["secret"]}, previousScreen = "fields";
let items = [1], fields = [1], itemQueries = [1], openSearchGeneration = 1;
let itemId = "id", itemTitle = "title", itemGroup = "group", focusSearchOnResults = true;
let errorText = "old", approvalError = "old", decisionError = "old", recent = ["/vault"];
let opened = false, openedCount = 0, sent = [];
const service = {running: false, write(line) { if (JSON.parse(line).action === "shutdown") this.running = false; }}, strings = {t: x => x};
const panel = {loadedContent: {passwordField: {text: "secret"}}};
const searchTimer = {stop() {}}, revealTimer = {stop() {}};
const root = {open() { openedCount++; }, reviewRequest(id) { reviewRequest(id); }};
function clearReveal() {}
function send(value) { sent.push(value); }
''' + functions + review + r'''
serviceExited();
if (screen !== "recent" || errorText || serviceReady || requests.length || requestId || Object.keys(review).length || items.length || fields.length || panel.loadedContent.passwordField.text)
  throw Error("service exit retained stale state");
handle(JSON.stringify({action:"show-request", id:"1"}));
reviewRequest("1");
if (screen !== "recent" || openedCount) throw Error("stale approval opened");
openVault("/vault");
if (service.running || screen !== "password") throw Error("service started before unlock");
unlockVault("master");
if (!service.running || screen !== "checking") throw Error("restart not requested");
handle(JSON.stringify({action:"recent", recent:["/vault"]}));
if (screen !== "checking" || !serviceReady || pendingPassword || sent.length !== 1 || sent[0].password !== "master") throw Error("unlock not submitted");
handle(JSON.stringify({action:"open", error:"bad password"}));
if (service.running || !stoppingService) throw Error("failed unlock left service running");
serviceExited();
if (screen !== "password" || errorText !== "bad password") throw Error("unlock error not retained");
unlockVault("master");
handle(JSON.stringify({action:"recent", recent:["/vault"]}));
function searchItems() {}
handle(JSON.stringify({action:"open"}));
if (screen !== "items" || !service.running || recent[0] !== "/vault") throw Error("unlock did not finish");
handle(JSON.stringify({action:"locked"}));
if (service.running || !stoppingService) throw Error("lock did not stop service");
serviceExited();
if (screen !== "recent" || serviceReady || errorText) throw Error("lock did not return to recent");
openVault("/vault"); unlockVault("master"); service.running = false; serviceExited();
if (screen !== "failed" || errorText !== "service.incompatible" || pendingPassword) throw Error("restart failure not shown");
'''
        result = subprocess.run([node, "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
