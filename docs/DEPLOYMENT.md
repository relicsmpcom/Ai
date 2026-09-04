# Deploying

Three ways to run this, from least to most infrastructure.

## 1. GitHub Pages — no server at all

The engine imports nothing outside the Python standard library. That one
property makes something unusual possible: the whole platform can run inside
the visitor's browser through [Pyodide](https://pyodide.org) (CPython compiled
to WebAssembly), served from a static host.

```bash
python scripts/build_pages.py --out site
python -m http.server -d site 8000     # try it locally first
```

The build is three files plus the engine:

| file | what it is |
| --- | --- |
| `index.html` | the same UI the server build serves, unmodified except for one script tag |
| `boot.js` | loads Pyodide, unpacks the engine, and replaces the page's HTTP transport with a direct call into Python |
| `wia-package.zip` | the engine and its data — about 160 KB |

To publish it, enable Pages on the repository (**Settings → Pages → Source:
GitHub Actions**). The `pages.yml` workflow then builds and deploys on every
push, but only after the tests pass **and** the detector still holds its
false-positive rate — a broken model must not reach a public page.

### What this gets you

* **Free, permanently.** Static hosting, no dyno, nothing to wake up.
* **Nothing is uploaded.** Detection and rewriting happen on the reader's
  machine. For a tool people paste essays and client emails into, that is a
  real feature rather than a technicality, and the page says so while it boots.
* **It works offline** once cached, and from a USB stick.

### What it costs

* **First visit downloads ~10 MB** of Python runtime and takes a few seconds.
  Cached afterwards. The page shows progress rather than sitting blank.
* **It needs a CDN** for Pyodide itself. Self-host it if you would rather not
  depend on one: copy the [`pyodide` npm
  package](https://www.npmjs.com/package/pyodide) next to the site and set
  `window.WIA_PYODIDE_BASE` to that directory before `boot.js` loads.
* **The optional model backend is not available** in the browser — there is
  nowhere safe to put an API key on a static page, which is the correct
  outcome rather than a limitation to work around.

## 2. A host that runs Python — the real API

Anything that runs a container works. There is no database, no queue and no
state to persist, so the whole deployment is one process:

```bash
pip install -e ".[api]"
uvicorn wia.api:app --host 0.0.0.0 --port ${PORT:-8000}
```

Use this when you want callable endpoints for other software, or when you do
not want visitors downloading a Python runtime. Free tiers on the usual hosts
sleep when idle, which shows up as a slow first request.

## 3. GitHub Actions — no website

Run the CLI in CI instead of hosting anything: check the writing in a repo on
every pull request, or on a schedule.

```yaml
- run: pip install -e .
- run: wia analyze docs/README.md
- run: wia detect changelog.md --json > detection.json
```

## Keeping the browser build working

The static build breaks the moment something in the engine imports a
third-party package, and it breaks silently — in someone else's browser, not
in your tests. `scripts/check_browser_safe.py` fails the build if any module
outside `wia/api/` grows a module-level import that is not in the standard
library. It runs in CI and in the test suite.

If you genuinely need a dependency, put the feature behind a lazy import
inside the function that uses it (as `wia/humanizer/llm.py` does with
`anthropic`), or keep it in `wia/api/`, which the browser bundle excludes.
