#!/bin/bash
# Sign (Developer ID + hardened runtime) and package the filaxy.shop build into a
# distributable, drag-to-Applications DMG. All signing happens in /tmp because the
# project lives on an iCloud-synced Desktop, which re-stamps extended attributes
# and breaks codesign. Notarization is a separate step needing Apple credentials.
#
# Usage:
#   tools/release_dmg.sh            # sign + build DMG (in dist/)
#   tools/release_dmg.sh notarize   # also submit to Apple + staple (needs creds)
set -e
cd "$(dirname "$0")/.."

APP_SRC=".build/Filaxy PDF Converter.app"
# Developer ID signing identity (appears publicly in any notarized binary's
# signature, so it's not a secret). Override with FILAXY_SIGN_IDENTITY if needed.
IDENTITY="${FILAXY_SIGN_IDENTITY:-Developer ID Application: Othmaro Fallas Rojas (J3YC73HASU)}"
ENT="$(pwd)/tools/engine-entitlements.plist"
DMG="dist/Filaxy PDF Converter.dmg"
NOTARY_PROFILE="filaxy-notary"

[ -d "$APP_SRC" ] || { echo "✗ No existe '$APP_SRC'. Corré primero: ./build-app.sh direct"; exit 1; }

WORK="$(mktemp -d)"
APP="$WORK/Filaxy PDF Converter.app"
echo "→ 0/4  Copiando a /tmp (fuera de iCloud) y limpiando extended attributes…"
cp -R "$APP_SRC" "$APP"
xattr -cr "$APP"

echo "→ 1/4  Firmando binarios internos (dylibs/.so) — Developer ID + hardened runtime…"
find "$APP" -type f \( -name "*.dylib" -o -name "*.so" \) -print0 \
  | while IFS= read -r -d '' f; do
      codesign --force --timestamp --options runtime -s "$IDENTITY" "$f"
    done

echo "→ 2/4  Firmando el motor Python (con entitlements) y sellando la app…"
codesign --force --timestamp --options runtime --entitlements "$ENT" \
  -s "$IDENTITY" "$APP/Contents/Resources/engine/filaxy-engine"
codesign --force --timestamp --options runtime -s "$IDENTITY" "$APP"

echo "→ 3/4  Verificando la firma…"
codesign --verify --deep --strict --verbose=2 "$APP" 2>&1 | tail -3 || true
echo "   (spctl dirá 'rejected' hasta que se notarice — es normal)"
spctl -a -vvv --type exec "$APP" 2>&1 | tail -2 || true

echo "→ 4/4  Armando el DMG (arrastrar a Aplicaciones)…"
STAGE="$WORK/dmg"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
mkdir -p dist
rm -f "$DMG"
hdiutil create -volname "Filaxy PDF Converter" -srcfolder "$STAGE" \
  -ov -format UDZO "$WORK/out.dmg" >/dev/null
codesign --force --timestamp -s "$IDENTITY" "$WORK/out.dmg"
cp "$WORK/out.dmg" "$DMG"
rm -rf "$WORK"
echo "✓ DMG firmado: $DMG  ($(du -h "$DMG" | cut -f1))"

if [ "$1" = "notarize" ]; then
  echo ""
  echo "→ Notarizando con Apple (perfil de llavero: $NOTARY_PROFILE)…"
  xcrun notarytool submit "$DMG" --keychain-profile "$NOTARY_PROFILE" --wait
  echo "→ Grapando el ticket…"
  xcrun stapler staple "$DMG"
  xcrun stapler validate "$DMG" && echo "✓ Notarizado y grapado. Listo para filaxy.shop."
  spctl -a -vvv --type install "$DMG" 2>&1 | tail -2 || true
else
  echo ""
  echo "── NOTARIZACIÓN (paso con tus credenciales) ───────────────────────────"
  echo "1) UNA sola vez (vos ingresás tu app-specific password de"
  echo "   https://appleid.apple.com → Seguridad → contraseñas específicas):"
  echo ""
  echo "   xcrun notarytool store-credentials \"$NOTARY_PROFILE\" \\"
  echo "     --apple-id <TU-APPLE-ID> --team-id <TU-TEAM-ID> --password <APP-SPECIFIC-PASSWORD>"
  echo ""
  echo "2) Después:  tools/release_dmg.sh notarize"
  echo "───────────────────────────────────────────────────────────────────────"
fi
