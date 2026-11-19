#!/bin/sh
# Install the reviewed Bypass release after verifying its pinned archive hash.
set -eu

version=0.3.5
case "$(uname -m)" in
  x86_64|amd64)
    arch=amd64
    expected=54e72fa2b67680c7a343dc47d8a0d2448506cab676381e00cfe2587dd79ab27a
    ;;
  aarch64|arm64)
    arch=arm64
    expected=16b2531b2fd23bc128781c76b42e38cb38fa068dcae99d35e4ae0976f3659cfe
    ;;
  *) echo 'Unsupported CPU architecture.' >&2; exit 1 ;;
esac

archive="bypass_${version}_linux_${arch}.tar.gz"
url="https://github.com/yaroshevych/bypass/releases/download/v${version}/${archive}"
tmp_dir=$(mktemp -d)
tmp_install=
trap 'rm -rf "$tmp_dir"; if [ -n "$tmp_install" ]; then rm -f "$tmp_install"; fi' EXIT HUP INT TERM
curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
  --connect-timeout 15 --max-time 120 --max-filesize 40000000 --output "$tmp_dir/$archive" "$url"
printf '%s  %s\n' "$expected" "$tmp_dir/$archive" | sha256sum -c - >/dev/null
# Extract only the expected file, without trusting archive paths or permissions.
tar -xOzf "$tmp_dir/$archive" -- bypass > "$tmp_dir/bypass"
test -s "$tmp_dir/bypass"
bin_dir="$HOME/.local/bin"
mkdir -p "$bin_dir"
tmp_install=$(mktemp "$bin_dir/.bypass-install.XXXXXXXX")
install -m 0755 "$tmp_dir/bypass" "$tmp_install"
mv -f "$tmp_install" "$bin_dir/bypass"
tmp_install=
printf 'Installed Bypass %s\n' "$version"
