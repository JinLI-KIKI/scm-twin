"""
Geography helpers for the network atlas: one complete world, roads, road routing.

The map shows exactly one world, 360 degrees wide and Pacific-centred, cut in the
mid-Atlantic at WINDOW_WEST (so Asia sits in the middle, Europe/Africa on the left,
the Americas on the right). Every geometry is normalised into that window; lines that
cross the cut are split, polygons are clipped.

Data: Natural Earth (public domain) 1:50m countries and 1:10m roads, downloaded once
into data/geo/. Truck lanes are routed over the Natural Earth road network.
Needs: shapely, networkx (both installed with `pip install searoute`).
"""
import json
import math
import os
import urllib.request

import networkx as nx
from shapely.affinity import translate
from shapely.geometry import LineString, MultiPolygon, Polygon, box, shape
from shapely.ops import unary_union

WINDOW_WEST = -28.0                  # cut meridian (mid-Atlantic)
WINDOW_EAST = WINDOW_WEST + 360.0
LAT_SOUTH, LAT_NORTH = -60.0, 84.0   # Antarctica left out
NE_BASE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
EARTH_R = 6371.0088


def ne_file(geo_dir, name):
    path = os.path.join(geo_dir, name + ".geojson")
    if not os.path.exists(path):
        os.makedirs(geo_dir, exist_ok=True)
        print(f"downloading Natural Earth {name} ...")
        urllib.request.urlretrieve(NE_BASE + name + ".geojson", path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def disp_lon(lon):
    """Longitude inside the display window [WINDOW_WEST, WINDOW_EAST)."""
    return (lon - WINDOW_WEST) % 360.0 + WINDOW_WEST


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(a))


# ---------------------------------------------------------------- lines into the window
def window_segments(coords):
    """coords [[lon, lat], ...] (any longitudes). Returns Leaflet segments
    [[[lat, lon], ...], ...] inside the window, split where the line crosses the cut."""
    # 1) make longitudes continuous
    cont, prev = [], None
    for lon, lat in coords:
        if prev is not None:
            while lon - prev > 180:
                lon -= 360
            while lon - prev < -180:
                lon += 360
        cont.append((lon, lat))
        prev = lon
    # 2) walk the line, wrapping and splitting at the window edges
    shift = disp_lon(cont[0][0]) - cont[0][0]
    segs, cur = [], [(cont[0][1], cont[0][0] + shift)]
    for (lo1, la1), (lo2, la2) in zip(cont, cont[1:]):
        x1, x2 = lo1 + shift, lo2 + shift
        while x2 >= WINDOW_EAST or x2 < WINDOW_WEST:
            edge = WINDOW_EAST if x2 >= WINDOW_EAST else WINDOW_WEST
            t = (edge - x1) / (x2 - x1) if x2 != x1 else 0
            lat_e = la1 + t * (la2 - la1)
            cur.append((lat_e, edge))
            segs.append(cur)
            step = -360 if edge == WINDOW_EAST else 360
            shift += step
            x1, x2 = edge + step, x2 + step
            cur = [(lat_e, x1)]
        cur.append((la2, x2))
    segs.append(cur)
    return [[[round(a, 3), round(b, 3)] for a, b in s] for s in segs if len(s) > 1]


# ---------------------------------------------------------------- countries
def countries(geo_dir, tariffs, eu27, tol=0.03):
    gj = ne_file(geo_dir, "ne_50m_admin_0_countries")
    west = box(-180, -90, WINDOW_WEST, 90)
    east = box(WINDOW_WEST, -90, 180, 90)
    feats = []
    for ft in gj["features"]:
        p = ft["properties"]
        iso = p.get("ADM0_A3")
        if iso == "ATA":
            continue
        g = shape(ft["geometry"]).buffer(0)
        parts = [g.intersection(east), translate(g.intersection(west), xoff=360)]
        g = unary_union([x for x in parts if not x.is_empty]).simplify(tol, preserve_topology=True)
        if g.is_empty:
            continue
        polys = [g] if isinstance(g, Polygon) else [x for x in getattr(g, "geoms", []) if isinstance(x, Polygon)]
        coords = [[[[round(x, 2), round(y, 2)] for x, y in ring.coords]
                   for ring in [poly.exterior, *poly.interiors]] for poly in polys]
        key = "EU" if iso in eu27 else iso
        feats.append({"type": "Feature",
                      "properties": {"iso": iso, "name": p.get("NAME"),
                                     "tkey": key if key in tariffs else None},
                      "geometry": {"type": "MultiPolygon", "coordinates": coords}})
    return {"type": "FeatureCollection", "features": feats}


# ---------------------------------------------------------------- roads
class Roads:
    """Natural Earth 1:10m roads: a display layer of major highways, and a graph
    for routing truck lanes."""
    DISPLAY = {"Major Highway", "Beltway"}
    ROUTABLE = {"Major Highway", "Beltway", "Secondary Highway", "Road", "Bypass", "Unknown"}

    def __init__(self, geo_dir):
        gj = ne_file(geo_dir, "ne_10m_roads")
        self.lines = []  # (type, LineString)
        for ft in gj["features"]:
            t = ft["properties"].get("type")
            if t not in self.ROUTABLE or not ft["geometry"]:
                continue
            g = shape(ft["geometry"])
            for ls in ([g] if g.geom_type == "LineString" else list(g.geoms)):
                self.lines.append((t, ls))

    def display_layer(self, tol=0.02):
        out = []
        for t, ls in self.lines:
            if t not in self.DISPLAY:
                continue
            s = ls.simplify(tol)
            out.extend(window_segments([[x, y] for x, y in s.coords]))
        return out

    def route(self, a, b, pad=1.5, snap_km=40, join_km=4.0):
        """Shortest road path between two points {lat, lon}; None if no usable path."""
        bb = box(min(a["lon"], b["lon"]) - pad, min(a["lat"], b["lat"]) - pad,
                 max(a["lon"], b["lon"]) + pad, max(a["lat"], b["lat"]) + pad)
        G = nx.Graph()
        owner, ends = {}, []
        for i, (_, ls) in enumerate(self.lines):
            if not ls.intersects(bb):
                continue
            pts = [(round(x, 3), round(y, 3)) for x, y in ls.coords]
            for p in pts:
                owner.setdefault(p, i)
            ends += [(pts[0], i), (pts[-1], i)]
            for p, q in zip(pts, pts[1:]):
                if p != q:
                    G.add_edge(p, q, w=haversine_km(p[1], p[0], q[1], q[0]))
        if G.number_of_nodes() == 0:
            return None
        nodes = list(G.nodes)
        # Natural Earth lines often stop just short of the road they join: link every line
        # end to the nearest vertex of another line within `join_km` (slightly penalised).
        cell = {}
        for p in nodes:
            cell.setdefault((int(p[0] * 20), int(p[1] * 20)), []).append(p)
        for e, i in ends:
            cx, cy = int(e[0] * 20), int(e[1] * 20)
            best, bd = None, join_km
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for q in cell.get((cx + dx, cy + dy), []):
                        if owner.get(q) == i or q == e:
                            continue
                        d = haversine_km(e[1], e[0], q[1], q[0])
                        if d < bd:
                            best, bd = q, d
            if best is not None:
                G.add_edge(e, best, w=bd * 1.5)

        def nearest(pt):
            n = min(nodes, key=lambda q: (q[0] - pt["lon"]) ** 2 + (q[1] - pt["lat"]) ** 2)
            return n, haversine_km(pt["lat"], pt["lon"], n[1], n[0])

        (na, da), (nb, db) = nearest(a), nearest(b)
        if da > snap_km or db > snap_km:
            return None
        try:
            path = nx.shortest_path(G, na, nb, weight="w")
        except nx.NetworkXNoPath:
            return None
        coords = [[a["lon"], a["lat"]]] + [list(p) for p in path] + [[b["lon"], b["lat"]]]
        km = sum(haversine_km(p[1], p[0], q[1], q[0]) for p, q in zip(coords, coords[1:]))
        straight = haversine_km(a["lat"], a["lon"], b["lat"], b["lon"])
        if km > 3 * straight + 30:   # implausible detour -> treat as no route
            return None
        return coords, km
