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
let stoppingService = false, stopScreen = "recent", reloadFailed = false, isOwner = true, sessionCheckAction = "";
let searchGeneration = 0, showingAllItems = false, favoriteConsent = "", favoriteLossMessage = "";
let requests = ["1"], requestId = "1", review = {targets:["secret"]}, previousScreen = "fields";
let items = [1], fields = [1], itemQueries = [1], openSearchGeneration = 1;
let itemId = "id", itemTitle = "title", itemGroup = "group", focusSearchOnResults = true;
let errorText = "old", approvalError = "old", decisionError = "old", recent = ["/vault"];
let opened = false, openedCount = 0, sent = [];
const service = {running: false, write(line) { if (JSON.parse(line).action === "shutdown") this.running = false; }}, strings = {t: x => x};
const panel = {loadedContent: {passwordField: {text: "secret"}, queryField: {text: "query"}}};
const searchTimer = {stop() {}}, revealTimer = {stop() {}};
const sessionGuard = {running: false}, recentLoader = {running: false};
const root = {open() { openedCount++; }, reviewRequest(id) { reviewRequest(id); }};
function clearReveal() {}
function send(value) { sent.push(value); }
''' + functions + review + r'''
function unlock(password) {
  unlockVault(password)
  sessionGuard.running = false
  completeSessionCheck(0)
}
serviceExited();
if (screen !== "recent" || errorText || serviceReady || requests.length || requestId || Object.keys(review).length || items.length || fields.length || panel.loadedContent.passwordField.text)
  throw Error("service exit retained stale state");
handle(JSON.stringify({action:"show-request", id:"1"}));
reviewRequest("1");
if (screen !== "recent" || openedCount) throw Error("stale approval opened");
openVault("/vault");
if (service.running || screen !== "password") throw Error("service started before unlock");
unlock("master");
if (!service.running || screen !== "checking") throw Error("restart not requested");
handle(JSON.stringify({action:"recent", recent:["/vault"], sensitiveClipboard:true}));
if (screen !== "checking" || !serviceReady || pendingPassword || sent.length !== 1 || sent[0].password !== "master") throw Error("unlock not submitted");
handle(JSON.stringify({action:"open", error:"bad password"}));
if (service.running || !stoppingService) throw Error("failed unlock left service running");
serviceExited();
if (screen !== "password" || errorText !== "bad password") throw Error("unlock error not retained");
unlock("master");
handle(JSON.stringify({action:"recent", recent:["/vault"], sensitiveClipboard:true}));
function searchItems() {}
handle(JSON.stringify({action:"open"}));
if (screen !== "items" || !service.running || recent[0] !== "/vault") throw Error("unlock did not finish");
screen = "fields"; fields = [1]; itemId = "id"; itemTitle = "title";
handle(JSON.stringify({action:"reloaded"}));
if (screen !== "items" || fields.length || itemId || itemTitle || searchGeneration !== 1) throw Error("reload did not clear stale details");
handle(JSON.stringify({action:"locked"}));
if (service.running || !stoppingService) throw Error("lock did not stop service");
serviceExited();
if (screen !== "recent" || serviceReady || errorText) throw Error("lock did not return to recent");
openVault("/vault"); unlock("master"); handle(JSON.stringify({action:"recent", sensitiveClipboard:true}));
handle(JSON.stringify({action:"reload-failed"})); serviceExited();
if (screen !== "password" || errorText !== "vault.reload_failed") throw Error("reload failure not shown");
openVault("/vault"); unlock("master");
handle(JSON.stringify({action:"recent"}));
if (service.running || !stoppingService || pendingPassword || errorText !== "service.clipboard_upgrade") throw Error("old backend was not rejected");
serviceExited();
if (screen !== "failed") throw Error("old backend did not show failure");
openVault("/vault"); unlock("master"); service.running = false; serviceExited();
if (screen !== "failed" || errorText !== "service.incompatible" || pendingPassword) throw Error("restart failure not shown");
openVault("/vault"); unlockVault("master");
if (!sessionGuard.running || service.running) throw Error("unlock started before session check");
cancelPendingUnlock(); sessionGuard.running = false; completeSessionCheck(0);
if (pendingPassword || service.running || screen !== "password") throw Error("closing while checking restored pending unlock");
unlockVault("master");
sessionGuard.running = false; completeSessionCheck(42);
if (screen !== "blocked" || pendingPassword || service.running || errorText !== "service.old_session") throw Error("unsafe session did not block unlock");
completeSessionCheck(0);
if (screen !== "checking" || !recentLoader.running) throw Error("closing old session did not recover");
screen = "items"; service.running = true; serviceReady = true; fields = [1];
completeSessionCheck(42);
if (!stoppingService || service.running || fields.length) throw Error("unsafe session did not stop an active service");
serviceExited();
if (screen !== "blocked" || errorText !== "service.old_session") throw Error("unsafe session warning was lost");
'''
        result = subprocess.run([node, "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
