"""
Shared chrome for the report pages in docs/: page list, top navigation, page wrapper.

Every page is a self-contained HTML file (data embedded), so the site works on GitHub Pages,
from a local folder, and as a published preview. Pages link to each other with relative URLs.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASH = os.path.join(ROOT, "src", "dash")
REPO_URL = "https://github.com/jinli-kiki/scm-twin"

# (file in docs/, key, tab label, href used in links)
PAGES = [
    ("index.html", "overview", "Overview", "index.html"),
    ("atlas.html", "atlas", "Network atlas", "atlas.html"),
    ("lanes.html", "lanes", "Lanes & lead time", "lanes.html"),
    ("mwd.html", "mwd", "MWD", "mwd.html"),
    ("transfer.html", "transfer", "Transfer timing", "transfer.html"),
    ("business-case.html", "business", "Business case", "business-case.html"),
    ("finished-goods.html", "fg", "Finished goods", "finished-goods.html"),
    ("fg-live.html", "fglive", "FG simulator", "fg-live.html"),
    ("demand.html", "demand", "Demand & KPI", "demand.html"),
    ("footprint.html", "footprint", "Footprint", "footprint.html"),
    ("rules.html", "rules", "Rules register", "rules.html"),
]


def read(name):
    with open(os.path.join(DASH, name), encoding="utf-8") as f:
        return f.read()


def nav_html(active):
    tabs = []
    for _, key, label, href in PAGES:
        cur = ' aria-current="page"' if key == active else ""
        tabs.append(f'<a class="tab" href="{href}"{cur}>{label}</a>')
    return (
        '<header class="topbar">\n'
        '  <a class="brand" href="index.html"><span class="brand-mark" aria-hidden="true"></span>'
        '<span class="brand-name">scm-twin</span></a>\n'
        '  <nav class="tabs" aria-label="Report pages">' + "".join(tabs) + '</nav>\n'
        f'  <a class="repo" href="{REPO_URL}">GitHub</a>\n'
        '</header>\n'
        '<script>(function(){var a=document.querySelector(".topbar .tab[aria-current]");'
        'if(a){var n=a.parentElement;n.scrollLeft=a.offsetLeft-(n.clientWidth-a.clientWidth)/2;}})();</script>\n'
    )


def document(body):
    """Full HTML document for docs/ (GitHub Pages) and for extra files of a preview."""
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '</head>\n<body>\n' + body + '\n</body>\n</html>\n')
