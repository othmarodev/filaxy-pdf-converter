#!/bin/bash
# Assemble a proper macOS .app bundle from the SwiftPM executable.
# Mirrors the proven Filaxy Files pattern: a Bundle ID + Info.plist are required
# for a real app identity, and the bundle is staged in /tmp to avoid iCloud
# extended attributes that break codesigning under ~/Desktop.
set -e
cd "$(dirname "$0")"

APP_NAME="FilaxyPDFConverter"
DISPLAY_NAME="Filaxy PDF Converter"
BUNDLE_ID="app.filaxy.PDFConverter"
EXEC=".build/arm64-apple-macosx/debug/${APP_NAME}"

# ---- build variant -----------------------------------------------------------
#   direct   (default) → filaxy.shop: donations (PayPal + USDT) + Finder Quick Action
#   appstore           → Mac App Store: NO donations, NO Quick Action auto-install
VARIANT="${1:-direct}"
SWIFT_FLAGS=""
VARIANT_TAG=""
case "$VARIANT" in
  direct)   echo "→ Variant: DIRECT / filaxy.shop (donations + Quick Action)";;
  appstore) SWIFT_FLAGS="-Xswiftc -DAPP_STORE"; VARIANT_TAG=" (App Store)"
            echo "→ Variant: APP STORE (no donations / no Quick Action)";;
  *) echo "unknown variant '$VARIANT' — use: direct | appstore"; exit 1;;
esac
STAGE="/tmp/filaxy-pdfconv-${VARIANT}/${DISPLAY_NAME}.app"
LOCAL_OUT=".build/${DISPLAY_NAME}${VARIANT_TAG}.app"

echo "→ Engine regression guard (fidelity invariants)…"
PY=".venv/bin/python"; [ -x "$PY" ] || PY="python3"
"$PY" tests/regression.py   # aborts the build (set -e) if a fidelity fix regressed

echo "→ Compiling…"
swift build $SWIFT_FLAGS

echo "→ Wrapping into .app bundle (staged in /tmp)…"
rm -rf "$STAGE"
mkdir -p "$STAGE/Contents/MacOS" "$STAGE/Contents/Resources"
cp "$EXEC" "$STAGE/Contents/MacOS/${APP_NAME}"

# Localization bundles + icon, if present.
RES_SRC="Sources/${APP_NAME}/Resources"
if [ -d "$RES_SRC" ]; then
  for lproj in "$RES_SRC"/*.lproj; do
    [ -d "$lproj" ] && cp -R "$lproj" "$STAGE/Contents/Resources/"
  done
  [ -f "$RES_SRC/AppIcon.icns" ] && cp "$RES_SRC/AppIcon.icns" "$STAGE/Contents/Resources/AppIcon.icns"
  for png in "$RES_SRC"/*.png; do [ -f "$png" ] && cp "$png" "$STAGE/Contents/Resources/"; done
fi

# Bundle the conversion engine. Prefer the FROZEN, self-contained binary
# (tools/freeze_engine.sh → dist/filaxy-engine/) so the .app runs fully offline
# with no Python/venv and is distributable. Fall back to the Python sources for
# dev (the app then resolves the project venv).
mkdir -p "$STAGE/Contents/Resources/engine"
if [ -x "dist/filaxy-engine/filaxy-engine" ]; then
  echo "   • bundling FROZEN engine (self-contained)…"
  cp -R dist/filaxy-engine/. "$STAGE/Contents/Resources/engine/"
else
  echo "   • bundling dev engine sources (falls back to venv) — run tools/freeze_engine.sh for a self-contained build"
  cp engine/*.py "$STAGE/Contents/Resources/engine/"
fi

cat > "$STAGE/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>            <string>${APP_NAME}</string>
    <key>CFBundleIdentifier</key>            <string>${BUNDLE_ID}</string>
    <key>CFBundleName</key>                  <string>${DISPLAY_NAME}</string>
    <key>CFBundleDisplayName</key>           <string>${DISPLAY_NAME}</string>
    <key>CFBundlePackageType</key>           <string>APPL</string>
    <key>CFBundleShortVersionString</key>    <string>0.1.0</string>
    <key>CFBundleVersion</key>               <string>1</string>
    <key>LSMinimumSystemVersion</key>        <string>13.0</string>
    <key>NSHighResolutionCapable</key>       <true/>
    <key>CFBundleIconFile</key>              <string>AppIcon</string>
    <key>LSApplicationCategoryType</key>     <string>public.app-category.productivity</string>
    <key>CFBundleDocumentTypes</key>
    <array>
        <dict>
            <key>CFBundleTypeName</key>        <string>PDF</string>
            <key>CFBundleTypeRole</key>        <string>Viewer</string>
            <key>LSHandlerRank</key>          <string>Alternate</string>
            <key>LSItemContentTypes</key>     <array><string>com.adobe.pdf</string></array>
        </dict>
    </array>
</dict>
</plist>
PLIST

echo "→ Ad-hoc codesigning…"
codesign --force --deep --sign - "$STAGE" 2>/dev/null || echo "  (skipped: codesign unavailable)"

echo "→ Installing to .build/ …"
rm -rf "$LOCAL_OUT"
mkdir -p .build
cp -R "$STAGE" "$LOCAL_OUT"

echo "→ Registering with LaunchServices…"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
  -f "$LOCAL_OUT" 2>/dev/null || true

echo "✓ Built: $LOCAL_OUT"
