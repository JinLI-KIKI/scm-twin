"""
Build the network atlas (docs/index.html) from the editable data files.

Inputs  data/nodes.csv, data/tariffs.csv, data/leadtime_params.csv
        Natural Earth 1:110m countries (public domain), downloaded once to data/geo/
Outputs data/network.json   lanes with real sea-lane geometry, distances, lead-time steps
        docs/index.html     self-contained Leaflet map (open it in a browser, or GitHub Pages)

Sea lanes come from the open-source `searoute` package (pip install searoute), which routes
over a global maritime network and lets us close passages (Suez / Bab-el-Mandeb) to model the
Red Sea situation. Air lanes are great circles. Inland lanes are straight lines with a road
factor. Every time value is a PLACEHOLDER from data/leadtime_params.csv.

Run:  python3 src/build_map.py
"""
import csv
import json
import math
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
NE_URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
          "geojson/ne_110m_admin_0_countries.geojson")
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
        # Pacific-centred display: the Americas north of the equator sit east of Asia
        r["dlon"] = r["lon"] + 360 if r["country_iso3"] in ("USA", "MEX", "CAN") else r["lon"]
        nodes[r["node_id"]] = r
    params = {r["key"]: float(r["value"]) for r in read_csv("leadtime_params.csv")}
    tariffs = {r["iso3"]: r for r in read_csv("tariffs.csv")}
    return nodes, params, tariffs


def load_countries(tariffs):
    path = os.path.join(DATA, "geo", "ne_110m_admin_0_countries.geojson")
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        print("downloading Natural Earth countries ...")
        urllib.request.urlretrieve(NE_URL, path)
    with open(path, encoding="utf-8") as f:
        gj = json.load(f)

    def rnd(c):
        if isinstance(c[0], (int, float)):
            return [round(c[0], 2), round(c[1], 2)]
        return [rnd(x) for x in c]

    feats = []
    for ft in gj["features"]:
        p = ft["properties"]
        iso = p.get("ADM0_A3")
        if iso == "ATA":
            continue
        key = "EU" if iso in EU27 else iso
        feats.append({"type": "Feature",
                      "properties": {"iso": iso, "name": p.get("NAME"),
                                     "tkey": key if key in tariffs else None},
                      "geometry": {"type": ft["geometry"]["type"],
                                   "coordinates": rnd(ft["geometry"]["coordinates"])}})
    return {"type": "FeatureCollection", "features": feats}


# ----------------------------------------------------------------------------- geometry
def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(a))


def unwrap(coords, start_lon, end_lon):
    """coords: [[lon, lat], ...]. Make longitudes continuous, anchored to the display
    longitude of the start node, and check the end lands on the end node's display lon."""
    out, prev = [], None
    for lon, lat in coords:
        if prev is not None:
            while lon - prev > 180:
                lon -= 360
            while lon - prev < -180:
                lon += 360
        out.append([lon, lat])
        prev = lon
    shift = round((start_lon - out[0][0]) / 360) * 360
    out = [[lon + shift, lat] for lon, lat in out]
    gap = end_lon - out[-1][0]
    if abs(gap) > 5:  # lane reached the end node "the other way round" the globe
        raise ValueError(f"lane end lon {out[-1][0]:.1f} does not match node {end_lon:.1f}")
    return [[round(lat, 3), round(lon, 3)] for lon, lat in out]  # Leaflet order


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
    lanes = {}

    def add_lane(lid, mode, a, b, coords, km, extra=None):
        A, B = nodes[a], nodes[b]
        lanes[lid] = {"id": lid, "mode": mode, "from": a, "to": b, "km": round(km),
                      "nm": round(km / 1.852),
                      "path": unwrap(coords, A["dlon"], B["dlon"]), **(extra or {})}

    def truck_lane(a, b, via=None):
        A, B = nodes[a], nodes[b]
        pts = [A] + (via or []) + [B]
        km = sum(haversine_km(p["lat"], p["lon"], q["lat"], q["lon"])
                 for p, q in zip(pts, pts[1:])) * ROAD_FACTOR
        lid = f"T:{a}>{b}"
        add_lane(lid, "inland", a, b, [[p["lon"], p["lat"]] for p in pts], km)
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

    countries = load_countries(tariffs)
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
    payload = json.dumps({**net, "countries": countries}, separators=(",", ":"),
                         ensure_ascii=False).replace("</", "<\\/")
    body = tpl.replace("/*__LEAFLET_CSS__*/", leaflet_css).replace("/*__DATA__*/null", payload)
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    page = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, '
            'viewport-fit=cover">\n</head>\n<body>\n' + body + '\n</body>\n</html>\n')
    with open(os.path.join(ROOT, "docs", "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    frag = os.environ.get("ATLAS_FRAGMENT")  # optional: page body only, for embedding
    if frag:
        with open(frag, "w", encoding="utf-8") as f:
            f.write(body)

    print(f"{len(lanes)} lanes, {len(routes)} routes -> data/network.json, docs/index.html "
          f"({os.path.getsize(os.path.join(ROOT, 'docs', 'index.html')) / 1e6:.2f} MB)")
    for r in routes:
        if r["mode"] == "sea":
            print(f"  {r['origin']} -> {r['mgi']:<5} {r['variant']:<5} {r['nm']:>7,} nm "
                  f"{r['days']:>5} days")
    for f in feed:
        print(f"  parts feed: {f['name']:<40} {f['days']} days")


if __name__ == "__main__":
    build()
