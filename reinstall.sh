#!/bin/sh
# Install this checkout into the Omarchy shell and restart it to clear QML caches.
set -eu

source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
plugin_dir="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/bypass.widget"

omarchy plugin validate "$source_dir"
mkdir -p "$plugin_dir/i18n"
for file in Panel.qml WidgetCoordinator.qml qmldir manifest.json launch-edit.sh check-running-bypass.py install-bypass.sh register-menu.py LICENSE; do
  install -m 644 "$source_dir/$file" "$plugin_dir/$file"
  cmp -s "$source_dir/$file" "$plugin_dir/$file"
done
for file in "$source_dir"/i18n/*.json; do
  install -m 644 "$file" "$plugin_dir/i18n/$(basename "$file")"
  cmp -s "$file" "$plugin_dir/i18n/$(basename "$file")"
done
printf 'Installed and verified Bypass widget in %s\n' "$plugin_dir"

if omarchy-shell shell rescanPlugins; then
  omarchy restart shell
  printf 'Restarted Omarchy shell to load the installed widget.\n'
else
  printf 'Omarchy shell is not reachable; the widget will load when it starts.\n' >&2
  exit 1
fi
