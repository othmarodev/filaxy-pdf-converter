import SwiftUI
import WebKit
import AppKit

/// Public PayPal identifiers — safe to ship in the (public) repo. The client-id
/// and hosted-button id are designed to be visible in the page that renders the
/// button; no secret is embedded.
private let payPalClientID = "BAAyssFecBR1RMn8D0q43LK19GyqqAgFXbiDd9MyxECNUXqYQkW5JnAa214fpDR0q6PnOu8IKbyvlMWAH0"
private let payPalHostedButtonID = "ALUEC9LDLGZ3L"

/// Renders the official PayPal "hosted button" donation button inside the app
/// via a transparent WKWebView. The button draws in-app (premium, native feel);
/// when the user clicks it PayPal opens its checkout — which we hand off to the
/// system browser, where PayPal login/payment works reliably (popups and
/// cross-site cookies that a sandboxed WKWebView can't carry).
struct DonationWebView: NSViewRepresentable {
    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.defaultWebpagePreferences.allowsContentJavaScript = true
        let web = WKWebView(frame: .zero, configuration: config)
        web.setValue(false, forKey: "drawsBackground")   // transparent over the sheet
        web.uiDelegate = context.coordinator
        web.navigationDelegate = context.coordinator
        web.loadHTMLString(Self.html, baseURL: URL(string: "https://www.paypal.com"))
        return web
    }

    func updateNSView(_ nsView: WKWebView, context: Context) {}

    private static var html: String {
        """
        <!DOCTYPE html><html><head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
          html,body{margin:0;padding:0;background:transparent;overflow:hidden;
                    font-family:-apple-system,system-ui,sans-serif;}
          /* Shrink to ~0.68 from the TOP-CENTER so the button stays centered. */
          body{transform:scale(0.68);transform-origin:top center;}
          #paypal-container-\(payPalHostedButtonID){padding:2px 0;margin:0 auto;}
        </style></head><body>
        <div id="paypal-container-\(payPalHostedButtonID)"></div>
        <script src="https://www.paypal.com/sdk/js?client-id=\(payPalClientID)&components=hosted-buttons&disable-funding=venmo&currency=USD"></script>
        <script>
          paypal.HostedButtons({ hostedButtonId: "\(payPalHostedButtonID)" })
                .render("#paypal-container-\(payPalHostedButtonID)");
        </script>
        </body></html>
        """
    }

    /// Hands the PayPal checkout off to the default browser instead of trying to
    /// complete it inside the embedded web view.
    final class Coordinator: NSObject, WKUIDelegate, WKNavigationDelegate {
        // PayPal opens checkout via window.open → intercept and send to browser.
        func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                     for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
            if let url = navigationAction.request.url { NSWorkspace.shared.open(url) }
            return nil
        }

        // If instead it does a top-level navigation to PayPal checkout, also
        // open externally and keep the in-app view on the button.
        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            if navigationAction.navigationType == .linkActivated,
               let url = navigationAction.request.url {
                NSWorkspace.shared.open(url)
                decisionHandler(.cancel)
                return
            }
            decisionHandler(.allow)
        }
    }
}
