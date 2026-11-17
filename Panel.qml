import QtQuick
import QtCore
import QtQuick.Controls
import QtQuick.Controls as Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import Quickshell
import Quickshell.Io
import qs.Ui
import qs.Ui as Ui
import qs.Commons
import qs.Commons as Commons
import "." as Plugin

Panel {
  id: root
  moduleName: "bypass.vault"
  ipcTarget: "bypass.vault"
  readonly property bool isOwner: Plugin.WidgetCoordinator.owner === root
  visible: isOwner
  implicitWidth: isOwner ? button.implicitWidth : 0
  implicitHeight: isOwner ? button.implicitHeight : 0
  Component.onCompleted: Plugin.WidgetCoordinator.attach(root)
  Component.onDestruction: {
    findBackend.running = false
    recentLoader.running = false
    installer.running = false
    service.running = false
    Plugin.WidgetCoordinator.detach(root)
  }
  onIsOwnerChanged: {
    if (isOwner) {
      backendPath = ""
      screen = "checking"
      findBackend.running = true
    }
  }
  property string screen: "checking"
  property string backendPath: ""
  property bool serviceReady: false
  property string pendingPassword: ""
  property bool stoppingService: false
  property string stopScreen: "recent"
  property string vaultPath: ""
  property string itemId: ""
  property string itemTitle: ""
  property string itemGroup: ""
  property bool itemFavorite: false
  property bool favoritePending: false
  property string favoriteConsent: ""
  property string favoriteLossMessage: ""
  property string errorText: ""
  property string approvalError: ""
  property string decisionError: ""
  property var recent: []
  property string recentQuery: ""
  readonly property var filteredRecent: recent.filter(path => path.toLowerCase().includes(recentQuery.toLowerCase().trim()))
  property var items: []
  property bool showingAllItems: false
  property var itemQueries: []
  property int searchGeneration: 0
  property int openSearchGeneration: -1
  property var fields: []
  property var requests: []
  property string requestId: ""
  property var review: ({})
  property string previousScreen: "recent"
  property var revealedValues: ({})
  property var revealRequests: []
  property int revealGeneration: 0
  property bool revealing: false
  property bool focusSearchOnResults: false
  Commons.Translations { id: strings; directory: Qt.resolvedUrl("i18n") }

  component BodyText: Text {
    textFormat: Text.PlainText
    color: Commons.Color.foreground
    font.family: Style.font.family
    font.pixelSize: Style.font.body
  }
  component WideButton: Ui.Button {
    id: wideButton
    property string navigationList: ""
    property int navigationIndex: -1
    Layout.fillWidth: true
    implicitHeight: Style.space(42)
    bordered: true
    focusable: true
    leftAlign: true
    Keys.onUpPressed: function(event) {
      if (navigationIndex < 0) { event.accepted = false; return }
      root.moveList(navigationList, navigationIndex, -1)
      event.accepted = true
    }
    Keys.onDownPressed: function(event) {
      if (navigationIndex < 0) { event.accepted = false; return }
      root.moveList(navigationList, navigationIndex, 1)
      event.accepted = true
    }
  }

  onOpenedChanged: {
    if (opened) {
      Qt.callLater(function() { if (root.opened && root.screen === "recent") panel.loadedContent.recentFilter.forceActiveFocus() })
    } else {
      if (panel.loadedContent) panel.loadedContent.passwordField.text = ""
      if (screen === "password" || (screen === "checking" && service.running)) stopService("recent")
      fields = []
      clearReveal()
      if (screen === "fields" || screen === "favorite-confirm") screen = "items"
      if (showingAllItems && service.running && screen === "items") {
        showingAllItems = false; searchTimer.stop(); searchGeneration++; openSearchGeneration = -1; searchItems("")
      }
      favoriteConsent = ""; favoriteLossMessage = ""
    }
  }
  onScreenChanged: {
    if (screen !== "fields") clearReveal()
    Qt.callLater(function() {
      if (!root.opened || !panel.loadedContent) return
      if (root.screen === "password") panel.loadedContent.passwordField.forceActiveFocus()
      else if (root.screen === "items") panel.loadedContent.queryField.forceActiveFocus()
      else if (root.screen === "recent") panel.loadedContent.recentFilter.forceActiveFocus()
      else if (root.screen === "favorite-confirm") panel.loadedContent.favoriteCancel.forceActiveFocus()
    })
  }

  function clearReveal() {
    revealGeneration++
    revealedValues = ({})
    revealing = false
    revealTimer.stop()
  }
  function toggleReveal() {
    if (revealing) { clearReveal(); return }
    clearReveal()
    const protectedFields = fields.filter(field => field.Protected)
    if (protectedFields.length === 0) return
    revealing = true
    for (const field of protectedFields) {
      revealRequests.push({id: itemId, field: field.Name, generation: revealGeneration})
      send({action: "reveal", id: itemId, field: field.Name})
    }
  }

  function send(value) {
    if (service.running) service.write(JSON.stringify(value) + "\n")
    else errorText = strings.t("service.unavailable")
  }
  function handle(line) {
    let result
    try { result = JSON.parse(line) } catch (e) { errorText = strings.t("service.invalid_response"); return }
    if (stoppingService) return
    if (result.action === "add-favorite") {
      favoritePending = false
      if (result.error) {
        if (result.consent && result.lossMessage && opened && screen === "fields" && result.id === itemId) {
          favoriteConsent = result.consent; favoriteLossMessage = result.lossMessage; screen = "favorite-confirm"
        } else if (opened && result.id === itemId) errorText = result.error
        return
      }
      favoriteConsent = ""; favoriteLossMessage = ""
      if (result.id === itemId) itemFavorite = true
      items = items.map(item => item.ID === result.id ? Object.assign({}, item, {Favorite: true}) : item)
      return
    }
    if (result.action === "approval-status") { approvalError = result.error || ""; return }
    if (result.action === "approve" || result.action === "deny") {
      if (result.error) decisionError = result.error
      return
    }
    if (result.action === "request") { requests = requests.concat([result.id]); return }
    if (result.action === "request-closed") {
      requests = requests.filter(id => id !== result.id)
      if (requestId === result.id) { requestId = ""; review = ({}); if (screen === "approval") screen = previousScreen }
      return
    }
    if (result.action === "show-request") { if (service.running && requests.includes(result.id)) { root.open(); root.reviewRequest(result.id) }; return }
    if (result.action === "reveal") {
      const request = revealRequests.shift()
      if (!request || request.generation !== revealGeneration || !opened || screen !== "fields" || request.id !== itemId) return
      if (result.error) { clearReveal(); errorText = result.error; return }
      if (result.id !== request.id || result.field !== request.field) return
      const values = Object.assign({}, revealedValues)
      values[result.field] = result.value || ""
      revealedValues = values
      const duration = Math.max(1, Math.min(10, result.remaining || 10)) * 1000
      if (!revealTimer.running || duration < revealTimer.interval) {
        revealTimer.interval = duration
        revealTimer.restart()
      }
      return
    }
    if (result.action === "recent" && !result.error) {
      serviceReady = true
      if (screen === "checking" && service.running) {
        const password = pendingPassword
        pendingPassword = ""
        send({action: "open", path: vaultPath, password: password})
      }
    }
    if (result.action === "items") {
      result.searchGeneration = itemQueries.shift()
      if (result.searchGeneration !== searchGeneration || screen !== "items") return
    }
    errorText = result.error || ""
    if (result.error) {
      if (result.action === "items") openSearchGeneration = -1
      if (result.action === "open") stopService("password")
      return
    }
    if (result.action === "recent") {
      recent = result.recent || []

    }
    else if (result.action === "open") { showingAllItems = false; recent = [vaultPath].concat(recent.filter(path => path !== vaultPath)).slice(0, 10); screen = "items"; focusSearchOnResults = true; searchItems("") }
    else if (result.action === "items") {
      const generation = result.searchGeneration
      items = result.items || []
      if (openSearchGeneration === generation) {
        openSearchGeneration = -1
        if (items.length > 0) openItem(items[0])
        return
      }
      if (focusSearchOnResults) {
        focusSearchOnResults = false
        Qt.callLater(function() {
          if (root.opened && root.screen === "items" && panel.loadedContent)
            panel.loadedContent.queryField.forceActiveFocus()
        })
      }
    }
    else if (result.action === "fields") {
      fields = (result.fields || []).filter(field => field.Name !== "Title")
      itemGroup = fields.length > 0 && fields[0].group ? fields[0].group : ""
      screen = "fields"
    }
    else if (result.action === "review" && result.id === requestId && screen === "approval") review = result
    else if (result.action === "lock" || result.action === "locked") stopService("recent")
  }
  function displayPath(path) {
    const home = decodeURIComponent(StandardPaths.writableLocation(StandardPaths.HomeLocation).toString().replace(/^file:\/\//, "")).replace(/\/$/, "")
    return home && (path === home || path.startsWith(home + "/")) ? "~" + path.slice(home.length) : path
  }
  function openVault(path) {
    errorText = ""
    vaultPath = path; screen = "password"
  }
  function unlockVault(password) {
    if (service.running || stoppingService) return
    errorText = ""; pendingPassword = password; screen = "checking"; service.running = true
  }
  function stopService(nextScreen) {
    pendingPassword = ""
    stopScreen = nextScreen
    stoppingService = true
    if (service.running) {
      screen = "checking"
      if (serviceReady) service.write(JSON.stringify({action: "shutdown"}) + "\n")
      else service.running = false
    }
    else { serviceExited() }
  }
  function serviceExited() {
    const wasReady = serviceReady
    const expected = stoppingService
    stoppingService = false
    serviceReady = false
    pendingPassword = ""
    requests = []; requestId = ""; review = ({}); previousScreen = "recent"
    items = []; fields = []; itemQueries = []; revealRequests = []; openSearchGeneration = -1; showingAllItems = false
    itemId = ""; itemTitle = ""; itemGroup = ""; itemFavorite = false; favoritePending = false; favoriteConsent = ""; favoriteLossMessage = ""; focusSearchOnResults = false
    approvalError = ""; decisionError = ""
    searchTimer.stop(); clearReveal()
    if (panel.loadedContent) panel.loadedContent.passwordField.text = ""
    screen = expected ? stopScreen : wasReady ? "recent" : "failed"
    if (!expected) errorText = wasReady ? "" : strings.t("service.incompatible")
  }
  function openItem(item) { itemId = item.ID; itemTitle = item.Title; itemFavorite = !!item.Favorite; send({action: "fields", id: item.ID}) }
  function escapeView() {
    if (screen === "favorite-confirm") { favoriteConsent = ""; favoriteLossMessage = ""; screen = "fields"; return true }
    if (screen === "fields") { fields = []; screen = "items"; if (panel.loadedContent && panel.loadedContent.queryField.text === "") { showingAllItems = false; searchItems("") }; return true }
    if (screen === "items") { close(); return true }
    if (screen === "password") {
      if (panel.loadedContent) panel.loadedContent.passwordField.text = ""
      errorText = ""
      stopService("recent")
      return true
    }
    return false
  }
  function searchItems(query) {
    if (!service.running) { errorText = strings.t("service.unavailable"); return }
    itemQueries.push(searchGeneration)
    send({action: "items", query: query})
  }
  function acceptSearch() {
    searchTimer.stop()
    searchGeneration++
    openSearchGeneration = searchGeneration
    searchItems(panel.loadedContent.queryField.text)
  }
  Timer { id: searchTimer; interval: 120; repeat: false; onTriggered: root.searchItems(panel.loadedContent.queryField.text) }
  function showAllItems() {
    if (panel.loadedContent) { searchTimer.stop(); searchGeneration++; openSearchGeneration = -1; showingAllItems = true; searchItems("*") }
  }
  function moveList(list, index, direction) {
    if (!panel.loadedContent) return
    const content = panel.loadedContent
    const showAllVisible = list === "items" && content.showAllButton.visible
    const count = list === "recent" ? filteredRecent.length : list === "password" ? 3 : list === "fields" ? fields.length + 1 : items.length + (showAllVisible ? 2 : 1)
    let next = index + direction
    if (list === "items" && index < 0) next = direction > 0 ? 0 : count - 1
    else next = (next + count) % count
    if (list === "recent" && count === 0) { content.recentFilter.forceActiveFocus(); return }
    if (list === "items" && count === 1) { content.queryField.forceActiveFocus(); return }
    const target = list === "recent"
      ? content.recentRepeater.itemAt(next)
      : list === "password"
        ? [content.passwordBackButton, content.passwordField, content.unlockButton][next]
        : list === "fields"
          ? (next === 0 ? content.fieldsBackButton : content.fieldRepeater.itemAt(next - 1))
          : next === items.length && showAllVisible ? content.showAllButton : next >= items.length ? content.queryField : content.itemRepeater.itemAt(next)
    if (!target) return
    target.forceActiveFocus()
    content.ensureVisible(target)
  }
  function reviewRequest(id) { if (!service.running || !requests.includes(id)) return; if (screen !== "approval") previousScreen = screen; requestId = id; review = ({}); screen = "approval"; send({action: "review", id: id}) }
  function decideRequest(action) {
    if (!service.running) { decisionError = strings.t("service.unavailable"); return }
    const id = requestId
    decisionError = ""
    requests = requests.filter(request => request !== id)
    requestId = ""; review = ({}); screen = previousScreen
    send({action: action, id: id})
    close()
  }

  Timer { id: revealTimer; repeat: false; onTriggered: root.clearReveal() }

  Process {
    id: findBackend
    command: ["sh", "-c", "if command -v bypass >/dev/null 2>&1; then command -v bypass; elif [ -x \"$HOME/.local/bin/bypass\" ]; then printf '%s\\n' \"$HOME/.local/bin/bypass\"; else exit 1; fi"]
    stdout: SplitParser { onRead: data => root.backendPath = data.trim() }
    onExited: function(exitCode, exitStatus) {
      if (exitCode === 0 && root.backendPath !== "") {
        root.screen = "checking"
        recentLoader.running = true
      } else {
        root.screen = "missing"
      }
    }
  }
  Process {
    id: recentLoader
    command: [root.backendPath, "widget-recent"]
    stdout: SplitParser { onRead: function(data) {
      try { const result = JSON.parse(data); root.recent = result.recent || [] }
      catch (e) { root.errorText = strings.t("service.invalid_response") }
    } }
    onExited: function(exitCode, exitStatus) {
      if (exitCode === 0 && root.errorText === "") root.screen = "recent"
      else { root.screen = "failed"; root.errorText = strings.t("service.incompatible") }
    }
  }
  Process {
    id: installer
    command: ["bash", "-o", "pipefail", "-c", "curl -fsSL https://raw.githubusercontent.com/yaroshevych/bypass/main/install.sh | bash"]
    onExited: function(exitCode, exitStatus) {
      if (exitCode === 0) {
        registerMenu.running = true
        root.backendPath = ""
        root.screen = "checking"
        findBackend.running = true
      } else {
        root.screen = "missing"
        root.errorText = strings.t("install.failed")
      }
    }
  }
  Process {
    id: registerMenu
    command: ["python3", decodeURIComponent(Qt.resolvedUrl("register-menu.py").toString().replace(/^file:\/\//, ""))]
  }
  Process {
    id: editLauncher
    command: ["omarchy-launch-tui", root.backendPath, root.vaultPath]
    onExited: function(exitCode, exitStatus) {
      if (exitCode !== 0) root.errorText = strings.t("vault.launch_failed")
    }
  }
  Process {
    id: service
    command: [root.backendPath, "widget-service"]
    stdinEnabled: true
    stdout: SplitParser { onRead: data => root.handle(data) }
    onStarted: root.send({action: "recent"})
    onExited: root.serviceExited()
  }
  FileDialog {
    id: picker
    title: strings.t("vault.open")
    nameFilters: [strings.t("vault.kee_pass_filter"), strings.t("vault.all_files_filter")]
    onAccepted: root.openVault(decodeURIComponent(selectedFile.toString().replace(/^file:\/\//, "")))
  }
  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰌾"
    onPressed: root.toggle()
  }
  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: !panel.loadedContent ? null : root.screen === "password" ? panel.loadedContent.passwordField : root.screen === "items" ? panel.loadedContent.queryField : root.screen === "recent" ? panel.loadedContent.recentFilter : panel.loadedContent
    contentWidth: panel.fittedContentWidth(Style.space(380))
    contentHeight: panel.fittedContentHeight(panel.loadedContentHeight, Style.space(560))
    content: ScrollView {
      id: scroll
      property alias passwordField: password
      property alias unlockButton: unlockButton
      property alias passwordBackButton: passwordBackButton
      property alias fieldsBackButton: fieldsBackButton
      property alias favoriteCancel: favoriteCancel
      property alias fieldRepeater: fieldRows
      property alias queryField: searchField
      property alias recentRepeater: recentRows
      property alias itemRepeater: itemRows
      property alias showAllButton: showAllButton
      property alias recentFilter: recentFilter
      function ensureVisible(item) {
        const view = scroll.contentItem
        const y = item.mapToItem(contentColumn, 0, 0).y
        if (y < view.contentY) view.contentY = y
        else if (y + item.height > view.contentY + view.height)
          view.contentY = Math.min(Math.max(0, view.contentHeight - view.height), y + item.height - view.height)
      }
      implicitHeight: contentColumn.implicitHeight
      contentWidth: availableWidth
      clip: true
      Keys.priority: Keys.BeforeItem
      Keys.onEscapePressed: function(event) { event.accepted = root.escapeView() }
      Keys.onUpPressed: function(event) {
        if (root.screen !== "fields") { event.accepted = false; return }
        const view = scroll.contentItem
        if (view.contentY <= 0) { event.accepted = false; return }
        view.contentY = Math.max(0, view.contentY - Math.max(Style.space(42), view.height * 0.8))
        event.accepted = true
      }
      Keys.onDownPressed: function(event) {
        if (root.screen !== "fields") { event.accepted = false; return }
        const view = scroll.contentItem
        if (view.contentY + view.height >= view.contentHeight) { event.accepted = false; return }
        view.contentY = Math.min(view.contentHeight - view.height, view.contentY + Math.max(Style.space(42), view.height * 0.8))
        event.accepted = true
      }
      ColumnLayout {
        id: contentColumn
        width: scroll.availableWidth
        spacing: Style.space(14)
        RowLayout {
          Layout.fillWidth: true
          PanelHero {
            Layout.fillWidth: true
            title: "bypass"
            meta: strings.t("vault.subtitle")
            iconComponent: Component {
              BodyText { text: "󰌾"; font.pixelSize: Style.font.display }
            }
          }
          WideButton {
            Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
            Layout.fillWidth: false
            implicitHeight: Style.space(32)
            Layout.minimumHeight: Style.space(32)
            Layout.maximumHeight: Style.space(32)
            visible: true
            enabled: root.requests.length > 0
            opacity: root.requests.length > 0 ? 1 : 0.55
            text: strings.t("approval.requests") + " (" + root.requests.length + ")"
            onClicked: root.reviewRequest(root.requests[0])
          }
        }
        BodyText { visible: root.errorText !== ""; text: root.errorText; color: Commons.Color.urgent; wrapMode: Text.Wrap; Layout.fillWidth: true }
        BodyText { visible: root.approvalError !== ""; text: root.approvalError; color: Commons.Color.urgent; wrapMode: Text.Wrap; Layout.fillWidth: true }
        ColumnLayout {
          visible: root.screen === "missing" || root.screen === "installing" || root.screen === "failed" || root.screen === "checking"
          Layout.fillWidth: true
          BodyText {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            text: root.screen === "missing" ? strings.t("install.prompt") : root.screen === "installing" ? strings.t("install.progress") : root.screen === "checking" ? strings.t("service.checking") : ""
          }
          WideButton {
            visible: root.screen === "missing"
            text: strings.t("install.button")
            onClicked: { root.errorText = ""; root.screen = "installing"; installer.running = true }
          }
          WideButton {
            visible: root.screen === "missing"
            text: strings.t("install.cancel")
            onClicked: root.close()
          }
          WideButton {
            visible: root.screen === "failed"
            text: strings.t("service.retry")
            onClicked: { root.errorText = ""; root.backendPath = ""; root.screen = "checking"; findBackend.running = true }
          }
        }
        ColumnLayout {
          visible: root.screen === "recent"
          Layout.fillWidth: true
          spacing: Style.space(8)
          PanelSeparator { Layout.fillWidth: true }
          RowLayout {
            Layout.fillWidth: true
            spacing: Style.space(8)
            TextField {
              id: recentFilter
              placeholderText: strings.t("search")
              Layout.fillWidth: true
              Layout.minimumWidth: 0
              Layout.maximumHeight: implicitHeight
              onTextChanged: root.recentQuery = text
              Keys.onDownPressed: function(event) { root.moveList("recent", -1, 1); event.accepted = true }
              Keys.onUpPressed: function(event) { event.accepted = true }
              onAccepted: if (root.filteredRecent.length > 0) root.openVault(root.filteredRecent[0])
            }
            Ui.Button {
              text: strings.t("vault.open_button")
              iconText: "󰝰"
              bordered: true
              focusable: true
              Layout.minimumHeight: recentFilter.implicitHeight
              Layout.maximumHeight: recentFilter.implicitHeight
              onClicked: picker.open()
            }
          }
          PanelSectionHeader { text: strings.t("vault.recent"); Layout.fillWidth: true }
          Repeater {
            id: recentRows
            model: root.filteredRecent
            WideButton {
              id: recentButton
              required property string modelData
              required property int index
              navigationList: "recent"
              navigationIndex: index
              bordered: false
              implicitHeight: searchField.implicitHeight
              Layout.minimumHeight: searchField.implicitHeight
              Layout.maximumHeight: searchField.implicitHeight
              text: root.displayPath(modelData)
              iconText: "󰌾"
              onClicked: root.openVault(recentButton.modelData)
            }
          }
        }
        ColumnLayout {
          visible: root.screen === "password"
          Layout.fillWidth: true
          spacing: Style.space(8)
          PanelSeparator { Layout.fillWidth: true }
          WideButton {
            id: passwordBackButton
            text: strings.t("back")
            iconText: "󰁍"
            navigationList: "password"
            navigationIndex: 0
            implicitHeight: searchField.implicitHeight
            Layout.minimumHeight: searchField.implicitHeight
            Layout.maximumHeight: searchField.implicitHeight
            onClicked: { password.text = ""; root.stopService("recent") }
          }
          BodyText { text: root.displayPath(root.vaultPath); elide: Text.ElideMiddle; Layout.fillWidth: true }
          TextField {
            id: password
            placeholderText: strings.t("vault.password")
            password: true
            Layout.fillWidth: true
            Keys.onDownPressed: function(event) { root.moveList("password", 1, 1); event.accepted = true }
            Keys.onUpPressed: function(event) { root.moveList("password", 1, -1); event.accepted = true }
            Keys.onEscapePressed: function(event) { event.accepted = root.escapeView() }
            onAccepted: { root.unlockVault(text); text = "" }
          }
          WideButton { id: unlockButton; text: strings.t("vault.unlock"); navigationList: "password"; navigationIndex: 2; onClicked: { root.unlockVault(password.text); password.text = "" } }
        }
        ColumnLayout {
          visible: root.screen === "items" || root.screen === "fields"
          Layout.fillWidth: true
          spacing: Style.space(8)
          PanelSeparator { Layout.fillWidth: true }
          RowLayout {
            Layout.fillWidth: true
            spacing: Style.space(8)
            TextField {
              id: searchField
              visible: root.screen === "items"
              placeholderText: strings.t("search")
              Layout.fillWidth: true
              Layout.minimumWidth: 0
              Layout.maximumHeight: implicitHeight
              onTextChanged: { root.showingAllItems = false; root.searchGeneration++; root.openSearchGeneration = -1; searchTimer.restart() }
              Keys.onDownPressed: function(event) { root.moveList("items", -1, 1); event.accepted = true }
              Keys.onUpPressed: function(event) { root.moveList("items", -1, -1); event.accepted = true }
              Keys.onEscapePressed: function(event) { event.accepted = root.escapeView() }
              onAccepted: root.acceptSearch()
            }
            WideButton {
              id: fieldsBackButton
              visible: root.screen === "fields"
              text: strings.t("back")
              iconText: "󰁍"
              Layout.minimumWidth: 0
              implicitHeight: searchField.implicitHeight
              Layout.minimumHeight: searchField.implicitHeight
              Layout.maximumHeight: searchField.implicitHeight
              onClicked: root.escapeView()
            }
            Ui.Button {
              text: strings.t("vault.lock")
              iconText: "󰌾"
              bordered: true
              focusable: true
              Layout.minimumHeight: searchField.implicitHeight
              Layout.maximumHeight: searchField.implicitHeight
              onClicked: root.send({action: "lock"})
            }
          }
        }
        ColumnLayout {
          visible: root.screen === "items"
          Layout.fillWidth: true
          spacing: Style.space(8)
          PanelSectionHeader { visible: !root.showingAllItems; text: searchField.text === "" ? strings.t("vault.favorites") : strings.t("vault.results"); Layout.fillWidth: true }
          Repeater {
            id: itemRows
            model: root.items
            WideButton {
              id: itemButton
              required property var modelData
              required property int index
              bordered: false
              implicitHeight: searchField.implicitHeight
              Layout.minimumHeight: searchField.implicitHeight
              Layout.maximumHeight: searchField.implicitHeight
              navigationList: "items"
              navigationIndex: index
              text: modelData.Title
              iconText: "󰌋"
              onClicked: root.openItem(itemButton.modelData)
            }
          }
          WideButton {
            id: showAllButton
            visible: searchField.text === "" && !root.showingAllItems
            text: strings.t("vault.show_all")
            navigationList: "items"
            navigationIndex: root.items.length
            onClicked: root.showAllItems()
          }
        }
        ColumnLayout {
          visible: root.screen === "fields"
          Layout.fillWidth: true
          BodyText { text: root.itemTitle; font.pixelSize: Style.font.title; font.bold: true; elide: Text.ElideRight; Layout.fillWidth: true }
          Repeater {
            id: fieldRows
            model: root.fields
            ColumnLayout {
              id: fieldRow
              required property var modelData
              required property int index
              readonly property bool actionsHovered: fieldHover.hovered
              Layout.fillWidth: true
              HoverHandler { id: fieldHover }
              RowLayout {
                Layout.fillWidth: true
                BodyText { text: modelData.Name; color: Commons.Color.foreground; Layout.fillWidth: true }
                PanelActionButton { iconText: "󰌷"; tooltipText: "Copy bypass://" + (fieldRow.modelData.group ? fieldRow.modelData.group + "/" : "") + root.itemTitle + "#" + fieldRow.modelData.Name; focusable: true; opacity: fieldHover.hovered || activeFocus ? 1 : 0; onClicked: root.send({action: "copy-reference", id: root.itemId, field: modelData.Name}) }
              }
              RowLayout {
                Layout.fillWidth: true
                BodyText {
                  text: modelData.Protected ? (Object.prototype.hasOwnProperty.call(root.revealedValues, modelData.Name) ? root.revealedValues[modelData.Name] : "••••••••") : modelData.Value
                  color: Qt.darker(Commons.Color.foreground, 1.3)
                  wrapMode: modelData.Name === "Notes" ? Text.Wrap : Text.NoWrap
                  maximumLineCount: modelData.Name === "Notes" ? 5 : 1
                  elide: Text.ElideRight
                  Layout.fillWidth: true
                }
                PanelActionButton {
                  iconText: "󰆏"
                  tooltipText: strings.t("copy.value")
                  focusable: true
                  opacity: fieldRow.actionsHovered || activeFocus ? 1 : 0
                  onClicked: root.send({action: "copy", id: root.itemId, field: modelData.Name})
                }
              }
            }
          }
          RowLayout {
            Layout.fillWidth: true
            PanelActionButton {
              iconText: "󰏫"
              tooltipText: strings.t("vault.edit")
              focusable: true
              onClicked: { editLauncher.running = true; root.close() }
            }
            PanelActionButton {
              iconText: root.revealing ? "󰈉" : "󰈈"
              tooltipText: root.revealing ? strings.t("secret.hide") : strings.t("secret.reveal")
              focusable: true
              enabled: root.fields.some(field => field.Protected)
              onClicked: root.toggleReveal()
            }
            PanelActionButton {
              iconText: "󰓎"
              tooltipText: root.itemFavorite ? strings.t("vault.favorited") : strings.t("vault.add_favorite")
              focusable: true
              enabled: !root.itemFavorite && !root.favoritePending
              onClicked: { root.favoritePending = true; root.errorText = ""; root.send({action: "add-favorite", id: root.itemId}) }
            }
          }
        }
        ColumnLayout {
          visible: root.screen === "favorite-confirm"
          Layout.fillWidth: true
          spacing: Style.space(8)
          PanelSeparator { Layout.fillWidth: true }
          PanelSectionHeader { text: strings.t("metadata.title"); Layout.fillWidth: true }
          BodyText { text: root.favoriteLossMessage; wrapMode: Text.Wrap; Layout.fillWidth: true }
          WideButton { id: favoriteCancel; text: strings.t("metadata.cancel"); onClicked: root.escapeView() }
          WideButton {
            text: strings.t("metadata.confirm")
            onClicked: {
              const consent = root.favoriteConsent
              root.favoriteConsent = ""; root.favoriteLossMessage = ""; root.screen = "fields"
              root.favoritePending = true; root.errorText = ""
              root.send({action: "add-favorite", id: root.itemId, consent: consent})
            }
          }
        }
        ColumnLayout {
          visible: root.screen === "approval"
          Layout.fillWidth: true
          PanelSeparator { Layout.fillWidth: true }
          RowLayout {
            Layout.fillWidth: true
            spacing: Style.space(8)
            WideButton {
              text: strings.t("back")
              iconText: "󰁍"
              Layout.fillWidth: true
              implicitHeight: searchField.implicitHeight
              Layout.minimumHeight: searchField.implicitHeight
              Layout.maximumHeight: searchField.implicitHeight
              onClicked: { root.review = ({}); root.screen = root.previousScreen }
            }
            Item { Layout.fillWidth: true; Layout.minimumWidth: 0; implicitHeight: searchField.implicitHeight }
            Item { implicitWidth: Style.space(84); implicitHeight: searchField.implicitHeight }
          }
          PanelSectionHeader { text: strings.t("approval.title"); Layout.fillWidth: true }
          BodyText { text: strings.t("approval.agent").arg(root.review.agent || strings.t("approval.unknown")); Layout.fillWidth: true; wrapMode: Text.Wrap }
          BodyText { text: strings.t("approval.command").arg((root.review.command || []).join(" ")); Layout.fillWidth: true; wrapMode: Text.Wrap }
          BodyText { text: strings.t("approval.directory").arg(root.review.directory || ""); Layout.fillWidth: true; wrapMode: Text.Wrap }
          BodyText { text: strings.t("approval.identity_note"); wrapMode: Text.Wrap; Layout.fillWidth: true }
          ColumnLayout {
            visible: (root.review.targets || []).length > 0
            Layout.fillWidth: true
            Layout.topMargin: Style.space(12)
            Layout.bottomMargin: Style.space(8)
            spacing: Style.space(12)
            PanelSeparator { Layout.fillWidth: true }
            PanelSectionHeader { text: strings.t("approval.requested_secrets"); Layout.fillWidth: true }
            Repeater {
              model: root.review.targets || []
              BodyText { required property var modelData; text: modelData.Title + ": " + modelData.Field; Layout.fillWidth: true; wrapMode: Text.Wrap }
            }
          }
          WideButton { text: strings.t("approval.approve"); enabled: (root.review.targets || []).length > 0; onClicked: root.decideRequest("approve") }
          WideButton { text: strings.t("approval.deny"); onClicked: root.decideRequest("deny") }
        }
        BodyText { visible: root.decisionError !== ""; text: root.decisionError; color: Commons.Color.urgent; wrapMode: Text.Wrap; Layout.fillWidth: true }
      }
    }
  }
}
