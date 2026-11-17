#!/bin/sh
# Focus an existing Bypass terminal, or launch it with the selected vault.
window=$(hyprctl clients -j | jq -r '[.[] | select(.class == "org.omarchy.bypass") | select(.address | test("^0x[0-9a-fA-F]+$")) | [.address, (.workspace.id | tostring)]][0] | if . then @tsv else empty end')
if [ -n "$window" ]; then
  address=${window%%	*}
  workspace=${window#*	}
  case "$workspace" in
    ''|*[!0-9-]*) ;;
    *) hyprctl dispatch "hl.dsp.focus({workspace = \"$workspace\"})" >/dev/null ;;
  esac
  exec hyprctl dispatch "hl.dsp.focus({window = hl.get_window(\"address:$address\")})"
fi
omarchy-launch-tui "$1" "$2" </dev/null >/dev/null 2>&1 &
