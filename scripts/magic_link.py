#!/usr/bin/env python3
"""Print the magic link from the most recent dashboard_magic_link .eml in .lumonox/emails/."""

import email
import glob
import os
import quopri

f = max(glob.glob(".lumonox/emails/dashboard_magic_link-*.eml"), key=os.path.getmtime)
with open(f) as fp:
    msg = email.message_from_file(fp)
text = quopri.decodestring(msg.get_payload()).decode()
print(next(line for line in text.splitlines() if line.startswith("http")))
