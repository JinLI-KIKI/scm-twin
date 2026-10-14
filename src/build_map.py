"""
Build the network atlas (docs/atlas.html) from the editable data files.

Inputs  data/nodes.csv, data/tariffs.csv, data/leadtime_params.csv
        Natural Earth 1:50m countries and 1:10m roads (public domain), downloaded once to
        data/geo/ (git-ignored; only the processed result goes into docs/atlas.html)
Outputs data/network.json   lanes with real sea-lane geometry, distances, lead-time steps
        docs/atlas.html     self-contained Leaflet map with the site's top navigation

Sea lanes come from the open-source `searoute` package (pip install searoute), which routes
over a global maritime network and lets us close passages (Suez / Bab-el-Mandeb) to model the
Red Sea situation. Air lanes are great circles. Truck lanes follow the Natural Earth road
network (straight line x road factor where no road route is found). The map is one complete,
Pacific-centred world (see src/geo_layers.py). Every time value is a PLACEHOLDER from
data/leadtime_params.csv.

Run:  python3 src/build_map.py
"""
import csv
import json
import math
import os
import sys

import geo_layers as GL
import site_chrome as SITE

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
EU27 = ["AUT", "BEL", "BGR", "HRV", "CYP", "CZE", "DNK", "EST", "FIN", "FRA", "DEU", "GRC",
        "HUN", "IRL", "ITA", "LVA", "LTU", "LUX", "MLT", "NLD", "POL", "PRT", "ROU", "SVK",
        "SVN", "ESP", "SWE"]
EARTH_R = 6371.0088
ROAD_FACTOR = 1.3

ORIGINS = {
    "CN": {"factory": "F_CN", "port": "P_SHA", "airport": "A_PVG", "label": "China · Kunshan"},
    "ID": {"factory": "F_ID", "port": "P_JKT", "airport": "A_CGK", "label": "Indonesia · Cikarang"},
}
MGIS = {  # mgi: (dest port, dest airport, air hub or None, importing country for duty)
    "M_US": ("P_LAX", "A_LAX", None, "USA"),
    "M_EU": ("P_RTM", "A_AMS", None, "EU"),
    "M_UK": ("P_FXT", "A_LHR", None, "GBR"),
    "M_JP": ("P_YOK", "A_NRT", None, "JPN"),
    "M_BR": ("P_SSZ", "A_VCP", "A_FRA", "BRA"),
}
EUROPE_PORTS = {"P_RTM", "P_FXT"}


# ----------------------------------------------------------------------------- inputs
def read_csv(name):
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_inputs():
    nodes = {}
    for r in read_csv("nodes.csv"):
        r["lat"], r["lon"] = float(r["lat"]), float(r["lon"])
        r["dlon"] = GL.disp_lon(r["lon"])  # longitude inside the one-world display window
        nodes[r["node_id"]] = r
    params = {r["key"]: float(r["value"]) for r in read_csv("leadtime_params.csv")}
    tariffs = {r["iso3"]: r for r in read_csv("tariffs.csv")}
    return nodes, params, tariffs


haversine_km = GL.haversine_km


def great_circle(a, b, n=64):
    la1, lo1, la2, lo2 = map(math.radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    v1 = (math.cos(la1) * math.cos(lo1), math.cos(la1) * math.sin(lo1), math.sin(la1))
    v2 = (math.cos(la2) * math.cos(lo2), math.cos(la2) * math.sin(lo2), math.sin(la2))
    d = math.acos(max(-1, min(1, sum(x * y for x, y in zip(v1, v2)))))
    pts = []
    for i in range(n + 1):
        t = i / n
        s1, s2 = math.sin((1 - t) * d) / math.sin(d), math.sin(t * d) / math.sin(d)
        x, y, z = (s1 * p + s2 * q for p, q in zip(v1, v2))
        pts.append([math.degrees(math.atan2(y, x)), math.degrees(math.atan2(z, math.hypot(x, y)))])
    return pts, d * EARTH_R


def sea_route(sr, a, b, variant):
    restrictions = ["northwest"]
    if variant == "cape":
        restrictions += ["babalmandab", "suez", "panama"]
    r = sr.searoute([a["lon"], a["lat"]], [b["lon"], b["lat"]], units="km",
                    restrictions=restrictions, return_passages=True)
    coords = [[a["lon"], a["lat"]]] + r.geometry["coordinates"] + [[b["lon"], b["lat"]]]
    return coords, r.properties["length"], r.properties.get("traversed_passages", [])


# ----------------------------------------------------------------------------- build
def build():
    try:
        import searoute as sr
    except ImportError:
        sys.exit("This script needs the open-source searoute package:  pip install searoute")

    nodes, P, tariffs = load_inputs()
    geo_dir = os.path.join(DATA, "geo")
    roads = GL.Roads(geo_dir)
    lanes = {}

    def add_lane(lid, mode, a, b, coords, km, extra=None):
        segs = GL.window_segments(coords)
        end = segs[-1][-1][1]
        if abs(end - nodes[b]["dlon"]) > 2:
            raise ValueError(f"{lid}: lane ends at lon {end:.1f}, node is at {nodes[b]['dlon']:.1f}")
        lanes[lid] = {"id": lid, "mode": mode, "from": a, "to": b, "km": round(km),
                      "nm": round(km / 1.852), "path": segs, **(extra or {})}

    def truck_lane(a, b):
        A, B = nodes[a], nodes[b]
        routed = roads.route(A, B)
        if routed:
            coords, km = routed
        else:
            coords = [[A["lon"], A["lat"]], [B["lon"], B["lat"]]]
            km = haversine_km(A["lat"], A["lon"], B["lat"], B["lon"]) * ROAD_FACTOR
        lid = f"T:{a}>{b}"
        add_lane(lid, "inland", a, b, coords, km, {"road_routed": bool(routed)})
        return lid

    def air_lane(a, b):
        coords, km = great_circle(nodes[a], nodes[b])
        lid = f"A:{a}>{b}"
        add_lane(lid, "air", a, b, coords, km)
        return lid

    def ocean_lane(a, b, variant):
        coords, km, passages = sea_route(sr, nodes[a], nodes[b], variant)
        lid = f"S:{a}>{b}:{variant}"
        add_lane(lid, "sea", a, b, coords, km, {"variant": variant, "passages": passages})
        return lid

    sea_days = lambda km: km / (P["sea_speed_knots"] * 1.852 * 24) + P["sea_port_call_days"]
    truck_days = lambda km: max(1.0, math.ceil(km / P["truck_km_per_day"]))
    r1 = lambda x: round(x, 1)

    routes = []
    for o, O in ORIGINS.items():
        t_fp = truck_lane(O["factory"], O["port"])
        t_fa = truck_lane(O["factory"], O["airport"])
        for m, (port, apt, hub, tkey) in MGIS.items():
            country = nodes[m]["country_iso3"]
            t_pm = truck_lane(port, m)
            t_am = truck_lane(apt, m)
            variants = ["cape", "suez"] if port in EUROPE_PORTS else ["any"]
            for v in variants:
                s = ocean_lane(O["port"], port, "cape" if v == "cape" else "open")
                steps = [
                    ("Factory to port (truck)", truck_days(lanes[t_fp]["km"])),
                    ("Export handling & vessel wait", P["origin_sea_handling_days"]),
                    ("Ocean voyage", sea_days(lanes[s]["km"])),
                    ("Import clearance & discharge", P[f"dest_handling_days_{country}"]),
                    ("Port to MGI (truck)", truck_days(lanes[t_pm]["km"])),
                    ("MGI receiving", P["mgi_receiving_days"]),
                ]
                routes.append({"origin": o, "mgi": m, "mode": "sea", "variant": v,
                               "lanes": [t_fp, s, t_pm], "km": lanes[s]["km"],
                               "nm": lanes[s]["nm"],
                               "steps": [[k, r1(d)] for k, d in steps],
                               "days": r1(sum(d for _, d in steps))})
            # air
            legs = [air_lane(O["airport"], hub), air_lane(hub, apt)] if hub else \
                   [air_lane(O["airport"], apt)]
            km = sum(lanes[l]["km"] for l in legs)
            flight = math.ceil(km / (800 * 24) * 2) / 2
            steps = [
                ("Factory to airport (truck)", truck_days(lanes[t_fa]["km"])),
                ("Export build-up & clearance", P["origin_air_handling_days"]),
                ("Flight" + (" via " + nodes[hub]["code"] if hub else ""), flight +
                 (P["air_hub_transit_days"] if hub else 0)),
                ("Import clearance", P.get(f"air_dest_handling_days_{country}",
                                           P["air_dest_handling_days"])),
                ("Airport to MGI (truck)", truck_days(lanes[t_am]["km"])),
                ("MGI receiving", P["mgi_receiving_days"]),
            ]
            routes.append({"origin": o, "mgi": m, "mode": "air", "variant": "any",
                           "lanes": [t_fa] + legs + [t_am], "km": km, "nm": round(km / 1.852),
                           "steps": [[k, r1(d)] for k, d in steps],
                           "days": r1(sum(d for _, d in steps))})

    # parts feed into the new Indonesia site (R14: China parts keep flowing after transfer)
    tsh = lanes["T:F_CN>P_SHA"]["km"]
    tpa = lanes["T:F_CN>A_PVG"]["km"]
    sea = ocean_lane("P_SHA", "P_JKT", "open")
    tjf = truck_lane("P_JKT", "F_ID")
    air = air_lane("A_PVG", "A_CGK")
    taf = truck_lane("A_CGK", "F_ID")
    feed = [
        {"name": "Sea via Shanghai → Jakarta", "lanes": ["T:F_CN>P_SHA", sea, tjf],
         "steps": [["Factory to port (truck)", truck_days(tsh)],
                   ["Export handling & vessel wait", P["origin_sea_handling_days"]],
                   ["Ocean voyage", r1(sea_days(lanes[sea]["km"]))],
                   ["Import clearance", P["dest_handling_days_IDN"]],
                   ["Port to factory (truck)", truck_days(lanes[tjf]["km"])]]},
        {"name": "Air expedite via Pudong → Soekarno-Hatta", "lanes": ["T:F_CN>A_PVG", air, taf],
         "steps": [["Factory to airport (truck)", truck_days(tpa)],
                   ["Export build-up & clearance", P["origin_air_handling_days"]],
                   ["Flight", 1.0],
                   ["Import clearance", P["air_dest_handling_days"]],
                   ["Airport to factory (truck)", truck_days(lanes[taf]["km"])]]},
    ]
    for f in feed:
        f["days"] = r1(sum(d for _, d in f["steps"]))

    countries = GL.countries(geo_dir, tariffs, EU27)
    road_layer = roads.display_layer()
    net = {
        "nodes": nodes, "lanes": lanes, "routes": routes, "feed": feed,
        "tariffs": tariffs, "origins": ORIGINS,
        "mgis": {m: {"port": v[0], "airport": v[1], "hub": v[2], "tkey": v[3]}
                 for m, v in MGIS.items()},
    }
    with open(os.path.join(DATA, "network.json"), "w", encoding="utf-8") as f:
        json.dump(net, f, indent=1, ensure_ascii=False)

    # ---- render page
    with open(os.path.join(ROOT, "src", "map_template.html"), encoding="utf-8") as f:
        tpl = f.read()
    with open(os.path.join(ROOT, "src", "vendor", "leaflet-1.9.4.css"), encoding="utf-8") as f:
        leaflet_css = f.read()
    payload = json.dumps({**net, "countries": countries, "roads": road_layer,
                          "window": [GL.WINDOW_WEST, GL.WINDOW_EAST, GL.LAT_SOUTH, GL.LAT_NORTH]},
                         separators=(",", ":"),
                         ensure_ascii=False).replace("</", "<\\/")
    body = (tpl.replace("/*__LEAFLET_CSS__*/", leaflet_css).replace("/*__DATA__*/null", payload)
            .replace("/*__CHROME__*/", SITE.read("chrome.css")).replace("<!--__NAV__-->", SITE.nav_html("atlas")))
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    with open(os.path.join(ROOT, "docs", "atlas.html"), "w", encoding="utf-8") as f:
        f.write(SITE.document(body))
    frag = os.environ.get("ATLAS_FRAGMENT")  # optional: page body only, for embedding
    if frag:
        with open(frag, "w", encoding="utf-8") as f:
            f.write(body)

    print(f"{len(lanes)} lanes, {len(routes)} routes -> data/network.json, docs/atlas.html "
          f"({os.path.getsize(os.path.join(ROOT, 'docs', 'atlas.html')) / 1e6:.2f} MB)")
    for r in routes:
        if r["mode"] == "sea":
            print(f"  {r['origin']} -> {r['mgi']:<5} {r['variant']:<5} {r['nm']:>7,} nm "
                  f"{r['days']:>5} days")
    for f in feed:
        print(f"  parts feed: {f['name']:<40} {f['days']} days")
    for l in lanes.values():
        if l["mode"] == "inland":
            print(f"  truck {l['from']:>6} -> {l['to']:<6} {l['km']:>5} km  "
                  f"{'road network' if l['road_routed'] else 'straight line x road factor'}")


if __name__ == "__main__":
    build()
