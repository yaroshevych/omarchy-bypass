#!/usr/bin/env python3
"""Add the Bypass menu action while preserving the user's JSONC."""
import json
import os
from pathlib import Path
import tempfile

path = Path.home() / '.config/omarchy/extensions/omarchy-menu.jsonc'
path.parent.mkdir(parents=True, exist_ok=True)
source = path.read_text() if path.exists() else '{}\n'
# Mask comments without changing offsets, leaving quoted strings intact.
masked = list(source)
i = 0
quoted = False
while i < len(source):
    if quoted:
        if source[i] == '\\':
            i += 2
            continue
        if source[i] == '"':
            quoted = False
    elif source[i] == '"':
        quoted = True
    elif source[i:i+2] == '//':
        end = source.find('\n', i)
        end = len(source) if end < 0 else end
        masked[i:end] = ' ' * (end - i)
        i = end
        continue
    elif source[i:i+2] == '/*':
        end = source.find('*/', i + 2)
        if end < 0:
            raise ValueError('Unterminated menu comment')
        end += 2
        masked[i:end] = ' ' * (end - i)
        i = end
        continue
    i += 1
clean = ''.join(masked)
# JSONC permits a trailing comma.
end = len(clean.rstrip()) - 1
if end < 0 or clean[end] != '}':
    raise ValueError('Menu must be a JSON object')
last = end - 1
while last >= 0 and clean[last].isspace():
    last -= 1
parseable = clean[:last] + ' ' + clean[last+1:] if clean[last] == ',' else clean
items = json.loads(parseable)
if not isinstance(items, dict):
    raise ValueError('Menu must be a JSON object')
if 'bypass' not in items:
    comma = ',' if clean[last] not in '{,' else ''
    entry = '\n  "bypass": {"icon":"󰌋","label":"Bypass","action":"omarchy-launch-tui --app-id=org.omarchy.bypass-menu bypass"}\n'
    updated = source[:last+1] + comma + source[last+1:end] + entry + source[end:]
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.bypass-menu-')
    try:
        with os.fdopen(fd, 'w') as output:
            output.write(updated)
        if path.exists():
            os.chmod(temp, path.stat().st_mode & 0o777)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
