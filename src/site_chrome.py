"""
Shared chrome for the report pages in docs/: page list, top navigation, page wrapper.

Every page is a self-contained HTML file (data embedded), so the site works on GitHub Pages,
from a local folder, and as a published preview. Pages link to each other with relative URLs.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASH = os.path.join(ROOT, "src", "dash")
REPO_URL = "https://github.com/jinli-kiki/scm-twin"

# (file in docs/, key, tab label, href used in links, nav group)
PAGES = [
    ("index.html", "overview", "Overview", "index.html", "start"),
    ("year.html", "year", "Year run", "year.html", "start"),
    ("market.html", "market", "Market", "market.html", "start"),
    ("atlas.html", "atlas", "Atlas", "atlas.html", "network"),
    ("lanes.html", "lanes", "Lanes", "lanes.html", "network"),
    ("footprint.html", "footprint", "Footprint", "footprint.html", "network"),
    ("mwd.html", "mwd", "MWD", "mwd.html", "transfer"),
    ("transfer.html", "transfer", "Transfer", "transfer.html", "transfer"),
    ("business-case.html", "business", "Business case", "business-case.html", "transfer"),
    ("demand.html", "demand", "Demand & KPI", "demand.html", "transfer"),
    ("ramp.html", "ramp", "Ramp & boards", "ramp.html", "transfer"),
    ("finished-goods.html", "fg", "Finished goods", "finished-goods.html", "eol"),
    ("fg-live.html", "fglive", "FG sim", "fg-live.html", "eol"),
    ("rules.html", "rules", "Rules", "rules.html", "ref"),
]
GROUPS = {"start": "Start", "network": "Network", "transfer": "Transfer", "eol": "End of life", "ref": "Sources"}


def read(name):
    with open(os.path.join(DASH, name), encoding="utf-8") as f:
        return f.read()


def nav_html(active):
    tabs, group = [], None
    for _, key, label, href, g in PAGES:
        if group is not None and g != group:
            tabs.append(f'<span class="tab-sep" aria-hidden="true" title="{GROUPS[g]}"></span>')
        group = g
        cur = ' aria-current="page"' if key == active else ""
        tabs.append(f'<a class="tab" href="{href}"{cur} data-group="{g}">{label}</a>')
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
