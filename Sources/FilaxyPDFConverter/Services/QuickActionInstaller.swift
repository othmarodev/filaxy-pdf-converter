import Foundation
import AppKit

/// Installs the Finder Quick Action ("Convertir a Word con Filaxy") automatically
/// when the app launches — no manual setup. The action is a tiny Automator
/// workflow placed in ~/Library/Services that runs the app's own engine headless
/// (right-click a PDF → convert, without opening the app). It's (re)written only
/// when the app build or the resolved engine path changes.
enum QuickActionInstaller {
    static let actionName = "Convertir a Word con Filaxy"
    private static let stampKey = "quickAction.installedStamp"
    private static let scriptRevision = 3   // bump when the workflow script changes

    /// The Quick Action hands the PDFs to the app (which is signed and can reach
    /// the engine), instead of running the engine itself — the sandboxed service
    /// runner can't read the engine on a protected folder like the Desktop.
    private static var script: String {
        let bundleID = Bundle.main.bundleIdentifier ?? "app.filaxy.PDFConverter"
        return #"""
        #!/bin/bash
        files=("$@")
        if [ ! -t 0 ]; then
          while IFS= read -r line; do [ -n "$line" ] && files+=("$line"); done
        fi
        [ "${#files[@]}" -gt 0 ] && open -b "\#(bundleID)" "${files[@]}"
        """#
    }

    static func installIfNeeded() {
        let build = (Bundle.main.infoDictionary?["CFBundleVersion"] as? String) ?? "0"
        let stamp = "\(build)|r\(scriptRevision)"

        let installed = UserDefaults.standard.string(forKey: stampKey)
        if installed == stamp,
           FileManager.default.fileExists(atPath: workflowURL.path) {
            return    // already current
        }
        do {
            try write(script: script)
            UserDefaults.standard.set(stamp, forKey: stampKey)
            flushServices()
        } catch {
            NSLog("QuickActionInstaller: \(error.localizedDescription)")
        }
    }

    private static var workflowURL: URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Services/\(actionName).workflow")
    }

    private static func write(script: String) throws {
        let fm = FileManager.default
        let contents = workflowURL.appendingPathComponent("Contents")
        if fm.fileExists(atPath: workflowURL.path) { try fm.removeItem(at: workflowURL) }
        try fm.createDirectory(at: contents, withIntermediateDirectories: true)
        try plistData(workflowDict(script: script))
            .write(to: contents.appendingPathComponent("document.wflow"))
        try plistData(infoDict())
            .write(to: contents.appendingPathComponent("Info.plist"))
    }

    private static func plistData(_ dict: [String: Any]) throws -> Data {
        try PropertyListSerialization.data(fromPropertyList: dict, format: .xml, options: 0)
    }

    /// Tell the system to re-scan the Services directory so the action appears
    /// without a logout.
    private static func flushServices() {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/System/Library/CoreServices/pbs")
        p.arguments = ["-flush"]
        try? p.run()
    }

    // MARK: - Workflow plist

    private static func infoDict() -> [String: Any] {
        ["NSServices": [[
            "NSMenuItem": ["default": actionName],
            "NSMessage": "runWorkflowAsService",
            "NSRequiredContext": ["NSServiceCategory": "public.item"],
            "NSSendFileTypes": ["com.adobe.pdf"],
        ]]]
    }

    private static func workflowDict(script: String) -> [String: Any] {
        let action: [String: Any] = [
            "action": [
                "AMAccepts": ["Container": "List", "Optional": false,
                              "Types": ["com.apple.cocoa.path"]],
                "AMActionVersion": "2.0.3",
                "AMApplication": ["Automator"],
                "AMParameterProperties": [
                    "COMMAND_STRING": [:], "CheckedForUserDefaultShell": [:],
                    "inputMethod": [:], "shell": [:], "source": [:],
                ],
                "AMProvides": ["Container": "List", "Types": ["com.apple.cocoa.path"]],
                "ActionBundlePath": "/System/Library/Automator/Run Shell Script.action",
                "ActionName": "Run Shell Script",
                "ActionParameters": [
                    "COMMAND_STRING": script,
                    "CheckedForUserDefaultShell": true,
                    "inputMethod": 1,          // pass input "as arguments"
                    "shell": "/bin/bash",
                    "source": "",
                ],
                "BundleIdentifier": "com.apple.RunShellScript",
                "CFBundleVersion": "2.0.3",
                "CanShowSelectedItemsWhenRun": false,
                "CanShowWhenRun": true,
                "Category": ["AMCategoryUtilities"],
                "Class Name": "RunShellScriptAction",
                "InputUUID": "FILAXY-INPUT-0001",
                "Keywords": ["Shell"],
                "OutputUUID": "FILAXY-OUTPUT-0001",
                "UUID": "FILAXY-ACTION-0001",
                "UnlocalizedApplications": ["Automator"],
                "arguments": [
                    "0": ["default value": 0, "name": "inputMethod", "required": "0", "type": "0", "uuid": "0"],
                    "1": ["default value": "", "name": "source", "required": "0", "type": "0", "uuid": "1"],
                    "2": ["default value": false, "name": "CheckedForUserDefaultShell", "required": "0", "type": "0", "uuid": "2"],
                    "3": ["default value": "", "name": "COMMAND_STRING", "required": "0", "type": "0", "uuid": "3"],
                    "4": ["default value": "/bin/sh", "name": "shell", "required": "0", "type": "0", "uuid": "4"],
                ],
                "isViewVisible": 1,
            ],
            "isViewVisible": 1,
        ]
        return [
            "AMApplicationBuild": "523",
            "AMApplicationVersion": "2.10",
            "AMDocumentVersion": "2",
            "actions": [action],
            "connectors": [:],
            "workflowMetaData": [
                "applicationBundleIDsByPath": [:],
                "applicationPaths": [],
                "inputTypeIdentifier": "com.apple.Automator.fileSystemObject",
                "outputTypeIdentifier": "com.apple.Automator.nothing",
                "presentationMode": 11,
                "processesInput": 0,
                "serviceInputTypeIdentifier": "com.apple.Automator.fileSystemObject",
                "serviceOutputTypeIdentifier": "com.apple.Automator.nothing",
                "serviceApplicationBundleID": "",
                "serviceApplicationPath": "",
                "serviceInputTypeIdentifierAttributes": [
                    "com.apple.Automator.fileSystemObject.type": "com.adobe.pdf",
                ],
                "useAutomaticInputType": 0,
                "workflowTypeIdentifier": "com.apple.Automator.servicesMenu",
            ],
        ]
    }
}
