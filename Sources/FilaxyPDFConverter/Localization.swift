import Foundation

/// Every user-facing string, keyed. Each case carries its Spanish and English
/// text. Kept as a runtime table (rather than .strings/.lproj) because the app
/// is a hand-wrapped SwiftPM bundle and we want LIVE language switching — the
/// UI reads `settings.t(.key)`, which re-evaluates the moment the language
/// changes, with no relaunch and no bundle reload.
enum L10n {
    case appTitle
    case appSubtitle
    case brand

    // Drop zone
    case dropTitle
    case dropHintChoose
    case dropReady
    case convertButton

    // Working
    case working

    // Failure / validation
    case mustBePDF
    case back

    // Result — verdict + metrics
    case verdictPass
    case verdictReview
    case metricTextPresent
    case metricTextComplete
    case metricSensitive
    case metricSensitiveOK
    case metricSensitiveReview
    case metricFonts
    case metricFontsOK
    case metricFontsReview
    case metricGraphics
    case metricGraphicsOK
    case metricGraphicsReview
    case zonesToReview
    case convertAnother
    case showInFinder
    case openInWord
    case recentsTitle
    case recentsClear
    case pagesElapsed   // takes args, see helper below

    // Save panel
    case savePanelTitle
    case savePanelPrompt
    case savePanelMessage

    // Settings / Preferences
    case settingsTitle
    case settingsGeneral
    case settingsAbout
    case settingsLanguage
    case settingsAppearance
    case settingsSaveLocation
    case settingsSaveLocationHint
    case langSystem
    case langSpanish
    case langEnglish
    case appearanceSystem
    case appearanceLight
    case appearanceDark

    // Menus
    case menuFile
    case menuView
    case menuHelp
    case menuOpenPDF
    case menuConvert
    case menuRevealOutput
    case menuHelpHowItWorks
    case menuAboutApp

    // About / Help
    case aboutTagline
    case aboutBody
    case donateHeading
    case donateBody
    case cryptoHeading
    case cryptoWarning
    case copyAddress
    case copied
    case howItWorksTitle
    case howItWorksBody
    case close

    func value(_ lang: String) -> String {
        let es = lang == "es"
        switch self {
        case .appTitle:        return "Filaxy PDF Converter"
        case .appSubtitle:     return es ? "PDF → Word, fiel y verificado" : "PDF → Word, faithful and verified"
        case .brand:           return "Filaxy Labs"

        case .dropTitle:       return es ? "Arrastrá un PDF aquí" : "Drag a PDF here"
        case .dropHintChoose:  return es ? "o hacé clic para elegir" : "or click to choose"
        case .dropReady:       return es ? "Listo para convertir" : "Ready to convert"
        case .convertButton:   return es ? "Convertir a Word" : "Convert to Word"

        case .working:         return es ? "Convirtiendo y verificando fidelidad…" : "Converting and verifying fidelity…"

        case .mustBePDF:       return es ? "El archivo debe ser un PDF." : "The file must be a PDF."
        case .back:            return es ? "Volver" : "Back"

        case .verdictPass:     return es ? "Conversión fiel y verificada" : "Faithful, verified conversion"
        case .verdictReview:   return es ? "Revisión recomendada" : "Review recommended"
        case .metricTextPresent:   return es ? "Texto del original presente" : "Original text present"
        case .metricTextComplete:  return es ? "Completo" : "Complete"
        case .metricSensitive:     return es ? "Datos sensibles (números/fechas/correos)" : "Sensitive data (numbers/dates/emails)"
        case .metricSensitiveOK:   return es ? "Todos verificados" : "All verified"
        case .metricSensitiveReview: return es ? "por revisar" : "to review"
        case .metricFonts:         return es ? "Fuentes legibles en Word (glifos correctos)" : "Fonts legible in Word (correct glyphs)"
        case .metricFontsOK:       return es ? "Verificadas" : "Verified"
        case .metricFontsReview:   return es ? "Revisar" : "Review"
        case .metricGraphics:      return es ? "Gráficos del original (diseño, logos, sellos)" : "Original graphics (layout, logos, stamps)"
        case .metricGraphicsOK:    return es ? "Preservados" : "Preserved"
        case .metricGraphicsReview: return es ? "Revisar" : "Review"
        case .zonesToReview:       return es ? "Zonas a revisar (marcadas en rojo):" : "Zones to review (marked in red):"
        case .convertAnother:      return es ? "Convertir otro" : "Convert another"
        case .showInFinder:        return es ? "Mostrar en Finder" : "Show in Finder"
        case .openInWord:          return es ? "Abrir en Word" : "Open in Word"
        case .recentsTitle:        return es ? "Recientes" : "Recent"
        case .recentsClear:        return es ? "Limpiar" : "Clear"
        case .pagesElapsed:        return es ? "página(s)" : "page(s)"

        case .savePanelTitle:      return es ? "Guardar documento de Word" : "Save Word document"
        case .savePanelPrompt:     return es ? "Guardar" : "Save"
        case .savePanelMessage:    return es ? "Elegí dónde guardar el .docx convertido" : "Choose where to save the converted .docx"

        case .settingsTitle:       return es ? "Ajustes" : "Settings"
        case .settingsGeneral:     return es ? "General" : "General"
        case .settingsAbout:       return es ? "Acerca de" : "About"
        case .settingsLanguage:    return es ? "Idioma" : "Language"
        case .settingsAppearance:  return es ? "Apariencia" : "Appearance"
        case .settingsSaveLocation:    return es ? "Al convertir" : "When converting"
        case .settingsSaveLocationHint: return es ? "Se te preguntará dónde guardar cada archivo." : "You'll be asked where to save each file."
        case .langSystem:          return es ? "Según el sistema" : "Match system"
        case .langSpanish:         return es ? "Español" : "Spanish"
        case .langEnglish:         return es ? "Inglés" : "English"
        case .appearanceSystem:    return es ? "Automática (sistema)" : "Automatic (system)"
        case .appearanceLight:     return es ? "Clara" : "Light"
        case .appearanceDark:      return es ? "Oscura" : "Dark"

        case .menuFile:            return es ? "Archivo" : "File"
        case .menuView:            return es ? "Ver" : "View"
        case .menuHelp:            return es ? "Ayuda" : "Help"
        case .menuOpenPDF:         return es ? "Abrir PDF…" : "Open PDF…"
        case .menuConvert:         return es ? "Convertir a Word" : "Convert to Word"
        case .menuRevealOutput:    return es ? "Mostrar resultado en Finder" : "Show result in Finder"
        case .menuHelpHowItWorks:  return es ? "Cómo funciona" : "How it works"
        case .menuAboutApp:        return es ? "Acerca de Filaxy PDF Converter" : "About Filaxy PDF Converter"

        case .aboutTagline:        return es ? "Un producto de Filaxy Labs · Gratis" : "A Filaxy Labs product · Free"
        case .aboutBody:           return es
            ? "Convierte PDF a Word conservando imágenes, posiciones, fuentes y firmas — y verifica la fidelidad contra el original."
            : "Converts PDF to Word preserving images, positions, fonts and signatures — and verifies fidelity against the original."
        case .donateHeading:       return es ? "Apoyá el proyecto" : "Support the project"
        case .donateBody:          return es
            ? "Filaxy PDF Converter es gratis y siempre lo será. Si te resultó útil y querés ayudarme a seguir creando apps gratuitas, podés hacer una donación totalmente voluntaria y opcional. Cada aporte, por pequeño que sea, hace una gran diferencia. ¡Gracias por tu apoyo! 💛"
            : "Filaxy PDF Converter is free and always will be. If it helped you and you'd like to support me in building more free apps, you can make a completely voluntary and optional donation. Every contribution, however small, makes a big difference. Thank you for your support! 💛"
        case .cryptoHeading:       return es ? "O con cripto · USDT (TRC20)" : "Or with crypto · USDT (TRC20)"
        case .cryptoWarning:       return es
            ? "⚠️ Enviá únicamente USDT por la red TRON (TRC20). Usar otra red provocará la pérdida de los fondos."
            : "⚠️ Send only USDT on the TRON network (TRC20). Using another network will cause loss of funds."
        case .copyAddress:         return es ? "Copiar" : "Copy"
        case .copied:              return es ? "¡Copiado!" : "Copied!"
        case .howItWorksTitle:     return es ? "Cómo funciona" : "How it works"
        case .howItWorksBody:      return es
            ? """
            1. Arrastrá un PDF a la ventana, hacé clic para elegirlo, o clic derecho en Finder → Acciones rápidas → «Convertir a Word con Filaxy».
            2. Filaxy reconstruye cada página: los gráficos del original (bordes, logos, sellos, firmas) se preservan exactos y el texto queda editable encima, en su fuente y coordenadas originales.
            3. Elegí dónde guardar el .docx.
            4. La app verifica el resultado contra el PDF original y te muestra la fidelidad: texto presente, datos sensibles (números/fechas/correos), fuentes legibles y gráficos preservados.
            5. Abrí el resultado directo en Word o mostralo en Finder. Tus conversiones quedan en «Recientes».

            Todo corre local y privado — nada sale de tu Mac. Cambiá idioma (ES/EN) y apariencia (clara/oscura) cuando quieras. La app es gratis; si te sirve, podés donar (PayPal o USDT) desde «Acerca de».
            """
            : """
            1. Drag a PDF onto the window, click to choose one, or right-click in Finder → Quick Actions → "Convertir a Word con Filaxy".
            2. Filaxy rebuilds each page: the original graphics (borders, logos, stamps, signatures) are preserved exactly and the text sits editable on top, in its original font and coordinates.
            3. Choose where to save the .docx.
            4. The app verifies the result against the original PDF and shows the fidelity: text present, sensitive data (numbers/dates/emails), legible fonts and preserved graphics.
            5. Open the result straight in Word or show it in Finder. Your conversions stay under "Recent".

            Everything runs locally and private — nothing leaves your Mac. Switch language (ES/EN) and appearance (light/dark) anytime. The app is free; if it helps you, you can donate (PayPal or USDT) from "About".
            """
        case .close:               return es ? "Cerrar" : "Close"
        }
    }
}
