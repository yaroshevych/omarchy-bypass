# Bypass for Omarchy

Open a KeePass vault from the Omarchy bar with Bypass Secrets Manager. Browse
favorites, search entries, copy fields and references, and review `bypass run`
requests. The widget does not edit vault contents.

## Requirements

- Omarchy Quattro on Linux.
- Bypass 0.3.1 or later, with `widget-service` support.
- `curl` and `bash` if you install Bypass from the widget.

## Install

```sh
omarchy plugin add https://github.com/yaroshevych/omarchy-bypass.git --enable
```

Open the Bypass icon in the bar. If Bypass is missing, the widget offers to
run the official installer after you approve. The installer downloads the latest
release and installs `bypass` in `~/.local/bin`. It requires network access and
does not use elevated privileges. You can also install Bypass separately using
the [Bypass instructions](https://github.com/yaroshevych/bypass).

The widget runs `bypass widget-service` as a child process and communicates
with it over private pipes. It must remain in the bar to receive `bypass run`
approval requests. The vault locks after the Bypass idle timeout, and copied
values use the configured clipboard timeout.

## Remove

```sh
omarchy plugin remove bypass.vault
```

Removing the plugin does not uninstall Bypass or delete vaults.

## Development

Validate on an Omarchy machine:

```sh
omarchy plugin validate .
qmllint -I "$OMARCHY_PATH/shell" Panel.qml
```

Test with a disposable vault. Check installation and failure recovery, vault
search, copying, locking, approval requests, shell restart, and removal.
