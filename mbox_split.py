#!/usr/bin/env python3
# Split a Gmail Takeout mbox by X-Gmail-Labels, writing RAW BYTES to avoid
# UnicodeEncodeError in email.generator.

import getopt
import mailbox
import os
import re
import sys

# Windows-illegal filename chars + control chars
_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON","PRN","AUX","NUL",
             *(f"COM{i}" for i in range(1,10)),
             *(f"LPT{i}" for i in range(1,10))}

def safe_label(label: str, maxlen: int = 120) -> str:
    label = label.strip()
    label = _ILLEGAL.sub(".", label)
    label = label.replace("..", ".").strip(" .")
    if not label:
        label = "Archive"
    if label.upper() in _RESERVED:
        label = f"_{label}"
    if len(label) > maxlen:
        label = label[:maxlen].rstrip(" .")
    return label

def main(argv):
    in_mbox = "inbox.mbox"
    prefix = "split_"

    try:
        opts, _args = getopt.getopt(argv, "i:p:", ["infile=", "prefix="])
    except getopt.GetoptError:
        print("python split.py -i <infile> -p <prefix>", file=sys.stderr)
        sys.exit(2)

    for opt, arg in opts:
        if opt in ("-i", "--infile"):
            in_mbox = arg
        elif opt in ("-p", "--prefix"):
            prefix = arg

    print(f"Processing file - {in_mbox} with prefix = {prefix}")

    def box_for(filename: str, boxes: dict):
        if filename not in boxes:
            boxes[filename] = mailbox.mbox(filename, create=True)
        return boxes[filename]

    boxes = {}
    inbox_fn   = prefix + "Inbox.mbox"
    sent_fn    = prefix + "Sent.mbox"
    archive_fn = prefix + "Archive.mbox"
    spam_fn    = prefix + "Spam.mbox"   # keep spam instead of dropping it
    trash_fn   = prefix + "Trash.mbox"  # optional

    src = mailbox.mbox(in_mbox)

    try:
        n = 0
        for key in src.iterkeys():
            msg = src.get_message(key)
            raw = src.get_bytes(key, from_=True)  # includes the "From " line; preserves it

            labels = msg.get("X-Gmail-Labels")
            if not labels:
                box_for(archive_fn, boxes).add(raw)
                n += 1
                continue

            labels_lc = labels.lower()

            # Gmail system labels often show up like "\\Inbox", "\\Sent", etc.
            if "spam" in labels_lc:
                box_for(spam_fn, boxes).add(raw)
            elif "trash" in labels_lc:
                box_for(trash_fn, boxes).add(raw)
            elif "inbox" in labels_lc:
                box_for(inbox_fn, boxes).add(raw)
            elif "sent" in labels_lc:
                box_for(sent_fn, boxes).add(raw)
            else:
                ignored = {"important", "unread", "starred", "newsletters"}
                saved = False
                for label in (l.strip() for l in labels.split(",")):
                    ll = label.lower()
                    if ll in ignored or not ll:
                        continue
                    fn = prefix + safe_label(label) + ".mbox"
                    box_for(fn, boxes).add(raw)
                    saved = True
                    break
                if not saved:
                    box_for(archive_fn, boxes).add(raw)

            n += 1
            if n % 2000 == 0:
                print(f"{n} messages routed...", file=sys.stderr)

    finally:
        # Flush/close everything cleanly
        for b in boxes.values():
            try:
                b.flush()
            except Exception:
                pass
            b.close()
        src.close()

if __name__ == "__main__":
    main(sys.argv[1:])
