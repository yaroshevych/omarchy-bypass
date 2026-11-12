pragma Singleton
import QtQuick

QtObject {
  property var widgets: []
  readonly property var owner: widgets.length ? widgets[0] : null

  function attach(widget) {
    if (widgets.indexOf(widget) === -1) widgets = widgets.concat([widget])
  }

  function detach(widget) {
    widgets = widgets.filter(candidate => candidate !== widget)
  }
}
