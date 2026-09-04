/* Browser runtime: run the whole platform client-side, with no server.
 *
 * The engine imports nothing outside the Python standard library, which is the
 * only reason this is possible. Pyodide gives us CPython in WebAssembly; the
 * `wia` package is shipped alongside this file as a zip and unpacked straight
 * into the virtual filesystem, so there is no wheel install and no micropip
 * round-trip.
 *
 * The point of the exercise: nobody's essay is uploaded anywhere. Detection
 * and rewriting happen on the reader's own machine, and a static host can
 * serve the whole product.
 */
(function () {
  "use strict";

  var PYODIDE_VERSION = "314.0.6";
  // Overridable so the page can be self-hosted with no CDN dependency at all:
  // set window.WIA_PYODIDE_BASE before this script and point it at your copy.
  var BASE = window.WIA_PYODIDE_BASE ||
    ("https://cdn.jsdelivr.net/npm/pyodide@" + PYODIDE_VERSION + "/");
  var PACKAGE_URL = window.WIA_PACKAGE_URL || "wia-package.zip";

  var box = null;
  var ready = null;

  function say(message, kind) {
    if (!box) box = document.getElementById("boot");
    if (!box) return;
    box.hidden = false;
    box.className = kind || "";
    box.innerHTML = message;
  }

  function step(message, fraction) {
    say(message + ' <progress max="100" value="' + Math.round(fraction * 100) + '"></progress>');
  }

  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var tag = document.createElement("script");
      tag.src = src;
      tag.onload = resolve;
      tag.onerror = function () { reject(new Error("could not load " + src)); };
      document.head.appendChild(tag);
    });
  }

  async function boot() {
    document.body.classList.add("booting");
    step("Starting Python in your browser — nothing you paste is uploaded", 0.05);

    await loadScript(BASE + "pyodide.js");
    step("Loading the Python runtime (about 10 MB, cached after the first visit)", 0.25);

    var pyodide = await loadPyodide({ indexURL: BASE });
    step("Unpacking the writing engine", 0.75);

    var response = await fetch(PACKAGE_URL);
    if (!response.ok) throw new Error("could not fetch " + PACKAGE_URL);
    var archive = await response.arrayBuffer();
    pyodide.unpackArchive(archive, "zip");

    step("Warming up the detector", 0.9);
    var call = pyodide.runPython([
      "import json, sys",
      "sys.path.insert(0, '/home/pyodide')",
      "from wia.service import handle as _handle, ServiceError",
      "def _call(path, payload):",
      "    try:",
      "        return json.dumps(_handle(path, json.loads(payload)))",
      "    except ServiceError as exc:",
      "        return json.dumps({'__error__': exc.message})",
      "    except Exception as exc:",
      "        return json.dumps({'__error__': f'{type(exc).__name__}: {exc}'})",
      "_call",
    ].join("\n"));

    // Force the model to load now rather than inside the first click.
    call("/health", "{}");

    document.body.classList.remove("booting");
    say("Running entirely in this browser tab — your text is never uploaded. " +
        "<a href=\"#\" id=\"boot-hide\">hide</a>");
    var hide = document.getElementById("boot-hide");
    if (hide) hide.onclick = function (e) { e.preventDefault(); box.hidden = true; };
    return call;
  }

  function fail(error) {
    if (document.body) document.body.classList.remove("booting");
    say("<b>Could not start the in-browser engine.</b> " + String(error.message || error) +
        "<br>This build needs to download Python (Pyodide) from a CDN. If your " +
        "network blocks it, run the tool locally instead: <code>pip install wia " +
        "&amp;&amp; wia serve</code>.", "error");
    throw error;
  }

  // This script is loaded in <head>, so the body it wants to touch does not
  // exist yet. Start once the document is parsed — but resolve `ready` through
  // a promise created now, so a call made in between still waits correctly.
  ready = new Promise(function (resolve, reject) {
    function start() {
      boot().then(resolve, function (error) {
        try { fail(error); } catch (e) { /* reported to the page already */ }
        reject(error);
      });
    }
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", start);
    } else {
      start();
    }
  });

  // Installed synchronously, so any call made before Python is ready simply
  // waits for it instead of falling through to a fetch that would 404.
  window.wiaTransport = async function (path, body) {
    var call = await ready;
    var result = JSON.parse(call(path, JSON.stringify(body || {})));
    if (result && result.__error__) throw new Error(result.__error__);
    return result;
  };
})();
