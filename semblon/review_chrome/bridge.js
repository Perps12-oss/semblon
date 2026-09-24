/* Live host bridge. Snapshot mode: no-ops (buttons already disabled). */
(function () {
  "use strict";

  var mode = document.body && document.body.getAttribute("data-mode");
  if (mode !== "live") {
    window.semblonApply = function () {
      /* snapshot: forensic file is read-only */
      return { ok: false, reason: "snapshot" };
    };
    return;
  }

  /**
   * Host (Python) injects a real implementation via:
   *   window.semblonHostApply = function(msg) { ... }
   * or tkinterweb / WebView2 object binding.
   */
  window.semblonApply = function (msg) {
    if (typeof window.semblonHostApply === "function") {
      return window.semblonHostApply(msg);
    }
    if (window.chrome && window.chrome.webview && window.chrome.webview.postMessage) {
      window.chrome.webview.postMessage(msg);
      return { ok: true, via: "webview2" };
    }
    console.warn("semblonApply: no live host bound", msg);
    return { ok: false, reason: "no_host" };
  };
})();
