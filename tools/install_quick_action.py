#!/usr/bin/env python3
"""
Build + install a Finder Quick Action: right-click a PDF (or several) →
"Convertir a Word con Filaxy" → converts each to .docx beside it, headless
(without opening the app), then shows a notification.

It runs the project engine via the venv. NOTE: this works on this machine
because it points at the repo's venv; a distributable version needs the frozen
engine (see build-app.sh TODO).

Run:  python3 tools/install_quick_action.py
"""
import os, plistlib, shutil

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = "Convertir a Word con Filaxy"
DEST = os.path.expanduser(f"~/Library/Services/{NAME}.workflow")

SCRIPT = f'''#!/bin/bash
REPO="{REPO}"
PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || PY="python3"
cd "$REPO" || exit 1
n=0
for f in "$@"; do
  case "$f" in
    *.pdf|*.PDF)
      out="${{f%.*}}.docx"
      "$PY" -m engine.cli "$f" "$out" >/dev/null 2>&1 && n=$((n+1)) ;;
  esac
done
osascript -e "display notification \\"$n archivo(s) convertidos a Word\\" with title \\"Filaxy PDF Converter\\""
'''

action = {
    "action": {
        "AMAccepts": {"Container": "List", "Optional": False,
                      "Types": ["com.apple.cocoa.path"]},
        "AMActionVersion": "2.0.3",
        "AMApplication": ["Automator"],
        "AMParameterProperties": {
            "COMMAND_STRING": {}, "CheckedForUserDefaultShell": {},
            "inputMethod": {}, "shell": {}, "source": {},
        },
        "AMProvides": {"Container": "List", "Types": ["com.apple.cocoa.path"]},
        "ActionBundlePath": "/System/Library/Automator/Run Shell Script.action",
        "ActionName": "Run Shell Script",
        "ActionParameters": {
            "COMMAND_STRING": SCRIPT,
            "CheckedForUserDefaultShell": True,
            "inputMethod": 1,            # 1 = pass input "as arguments"
            "shell": "/bin/bash",
            "source": "",
        },
        "BundleIdentifier": "com.apple.RunShellScript",
        "CFBundleVersion": "2.0.3",
        "CanShowSelectedItemsWhenRun": False,
        "CanShowWhenRun": True,
        "Category": ["AMCategoryUtilities"],
        "Class Name": "RunShellScriptAction",
        "InputUUID": "FILAXY-INPUT-UUID-0001",
        "Keywords": ["Shell"],
        "OutputUUID": "FILAXY-OUTPUT-UUID-0001",
        "UUID": "FILAXY-ACTION-UUID-0001",
        "UnlocalizedApplications": ["Automator"],
        "arguments": {
            "0": {"default value": 0, "name": "inputMethod", "required": "0",
                  "type": "0", "uuid": "0"},
            "1": {"default value": "", "name": "source", "required": "0",
                  "type": "0", "uuid": "1"},
            "2": {"default value": False, "name": "CheckedForUserDefaultShell",
                  "required": "0", "type": "0", "uuid": "2"},
            "3": {"default value": "", "name": "COMMAND_STRING", "required": "0",
                  "type": "0", "uuid": "3"},
            "4": {"default value": "/bin/sh", "name": "shell", "required": "0",
                  "type": "0", "uuid": "4"},
        },
        "isViewVisible": 1,
    },
    "isViewVisible": 1,
}

wflow = {
    "AMApplicationBuild": "523",
    "AMApplicationVersion": "2.10",
    "AMDocumentVersion": "2",
    "actions": [action],
    "connectors": {},
    "workflowMetaData": {
        "applicationBundleIDsByPath": {},
        "applicationPaths": [],
        "inputTypeIdentifier": "com.apple.Automator.fileSystemObject",
        "outputTypeIdentifier": "com.apple.Automator.nothing",
        "presentationMode": 11,
        "processesInput": 0,
        "serviceInputTypeIdentifier": "com.apple.Automator.fileSystemObject",
        "serviceOutputTypeIdentifier": "com.apple.Automator.nothing",
        "serviceApplicationBundleID": "",
        "serviceApplicationPath": "",
        "serviceInputTypeIdentifierAttributes": {
            "com.apple.Automator.fileSystemObject.type": "com.adobe.pdf",
        },
        "useAutomaticInputType": 0,
        "workflowTypeIdentifier": "com.apple.Automator.servicesMenu",
    },
}

info = {
    "NSServices": [{
        "NSMenuItem": {"default": NAME},
        "NSMessage": "runWorkflowAsService",
        "NSRequiredContext": {"NSServiceCategory": "public.item"},
        "NSSendFileTypes": ["com.adobe.pdf"],
    }],
}

if os.path.exists(DEST):
    shutil.rmtree(DEST)
os.makedirs(f"{DEST}/Contents", exist_ok=True)
with open(f"{DEST}/Contents/document.wflow", "wb") as f:
    plistlib.dump(wflow, f)
with open(f"{DEST}/Contents/Info.plist", "wb") as f:
    plistlib.dump(info, f)

# nudge LaunchServices/pbs to pick up the new service
os.system("/System/Library/CoreServices/pbs -flush 2>/dev/null")
print("installed:", DEST)
