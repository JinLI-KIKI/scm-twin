"""
Generate the editable sample dataset for the MWD module.

Everything here is a PLACEHOLDER unless marked otherwise in docs/ASSUMPTIONS.md.
Edit the CSVs in data/ directly once real numbers are known; rerun this script
only if you want to reset to the defaults.

Structure
---------
- 2 platforms: P1 (current gen, collective EOL soon), P2 (next gen, NPI)
- 3 models:   P1-14, P1-16 on P1;  P2-14 on P2 (NPI)
- 6 locales:  US, UK, FR, DE, JP, BR
- SKU = model x locale  (18 SKUs)
"""
import csv, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")

LOCALES = [  # locale, share of each model's volume, power-cord family
    ("US", 0.40, "US"), ("UK", 0.08, "UK"), ("FR", 0.07, "EU"),
    ("DE", 0.12, "EU"), ("JP", 0.15, "JP"), ("BR", 0.18, "BR"),
]

PLATFORMS = [  # platform, collective_eol_week (overrides model EOL if earlier)
    ("P1", 30),
    ("P2", 156),
]

MODELS = [  # model, platform, npi_week, eol_week, peak_weekly_units, ramp_up_weeks, ramp_down_weeks,
            # customs_value_usd (per finished unit, tariff base), board_extra_usd (PCB, passives, SMT)
    ("P1-14", "P1", -52, 30, 5000, 4, 4, 480.0, 35.0),
    ("P1-16", "P1", -52, 30, 2000, 4, 4, 560.0, 38.0),
    ("P2-14", "P2", 26, 156, 6000, 4, 4, 520.0, 36.0),
]

# material_id, name, route_class, unit_cost_usd, lead_time_weeks, decay_type, rework_cost_usd, industry_standard
# industry_standard: 1 = same PN bought by other brands at shared ODMs -> short non-cancellable window
# route_class: 1 = same PN absorbed by other plans; 2 = convertible at a cost; 3 = locked -> MWD
# decay_type : physical (battery) | policy (date-code rule) | obsolescence (dies with EOL)
COMMON = [
    ("CPU_P1",      "CPU + chipset, platform P1",        1, 120.0, 16, "policy",       0, 1),
    ("CPU_P2",      "CPU + chipset, platform P2",        1, 135.0, 16, "policy",       0, 1),
    ("MEM_16G",     "16GB memory (shared P1 & P2)",      1,  40.0,  8, "policy",       0, 1),
    ("SSD_512",     "512GB SSD (shared P1 & P2)",        1,  35.0,  8, "policy",       0, 1),
    ("PANEL_14",    "14in panel (shared P1-14 & P2-14)", 1,  60.0, 12, "obsolescence", 0, 1),
    ("PANEL_16",    "16in panel (P1-16 only)",           1,  75.0, 12, "obsolescence", 0, 1),
    ("BATT_P1",     "Battery pack, platform P1 (custom)", 1, 30.0, 10, "physical",     0, 0),
    ("BATT_P2",     "Battery pack, platform P2 (custom)", 1, 32.0, 10, "physical",     0, 0),
    ("ADAPTER_65W", "65W adapter body (all models)",     1,  12.0,  6, "obsolescence", 0, 0),
]
STD_CANCEL_WINDOW = 2  # PLACEHOLDER weeks
HOUSING = {"P1-14": 40.0, "P1-16": 45.0, "P2-14": 42.0}

def main():
    os.makedirs(D, exist_ok=True)
    mats = list(COMMON)
    for m, h in HOUSING.items():
        mats.append((f"HOUSING_{m}", f"Housing set {m}", 1, h, 10, "obsolescence", 0, 0))
    for m, *_ in MODELS:
        for loc, _, _ in LOCALES:
            mats.append((f"KB_{m}_{loc}", f"Keyboard + C-cover {m} {loc}", 3, 25.0, 8, "obsolescence", 0, 0))
    for fam in sorted({c for _, _, c in LOCALES}):
        mats.append((f"CORD_{fam}", f"Power cord {fam} plug", 2, 2.0, 4, "obsolescence", 2.5, 0))
    for loc, _, _ in LOCALES:
        mats.append((f"PKG_{loc}", f"Box, manuals, labels {loc}", 2, 3.0, 2, "obsolescence", 1.0, 0))

    with open(os.path.join(D, "materials.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["material_id", "name", "route_class", "unit_cost_usd", "lead_time_weeks",
                    "decay_type", "rework_cost_usd", "industry_standard", "cancel_window_weeks",
                    "on_board"])
        for r in mats:
            # standard parts: ODM/supplier can redeploy to other brands -> short window (PLACEHOLDER 2w)
            # custom parts: nobody else can use them -> non-cancellable for the full lead time
            on_board = 1 if (r[0].startswith("CPU_") or r[0] == "MEM_16G") else 0
            w.writerow(list(r) + [STD_CANCEL_WINDOW if r[7] else r[4], on_board])

    with open(os.path.join(D, "platforms.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["platform", "collective_eol_week"]); w.writerows(PLATFORMS)

    with open(os.path.join(D, "models.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["model", "platform", "npi_week", "eol_week", "peak_weekly_units",
                    "ramp_up_weeks", "ramp_down_weeks", "customs_value_usd", "board_extra_usd"])
        w.writerows(MODELS)

    with open(os.path.join(D, "locales.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["locale", "share", "cord_family"]); w.writerows(LOCALES)

    platform_of = {m: p for m, p, *_ in MODELS}
    rows = []
    for m, *_ in MODELS:
        p = platform_of[m]
        for loc, _, fam in LOCALES:
            sku = f"{m}_{loc}"
            for mat in (f"CPU_{p}", "MEM_16G", "SSD_512", f"BATT_{p}", "ADAPTER_65W",
                        f"HOUSING_{m}", f"KB_{m}_{loc}", f"CORD_{fam}", f"PKG_{loc}"):
                rows.append((sku, mat, 1))
            rows.append((sku, "PANEL_16" if m.endswith("16") else "PANEL_14", 1))
    with open(os.path.join(D, "bom.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["sku", "material_id", "qty_per"]); w.writerows(rows)

    params = [
        ("liability_window_weeks", 16, "Practitioner input (virtualized): cancelled plan inside the window counts as MWD"),
        ("tracking_window_weeks", 156, "Practitioner input (virtualized): tracked 36 months, adjustable"),
        ("carrying_rate_annual", 0.20, "PLACEHOLDER"),
        ("battery_recharge_interval_weeks", 26, "Web: Apple, recharge to 50% every 6 months"),
        ("battery_recharge_cost_usd", 0.50, "PLACEHOLDER"),
        ("date_code_limit_weeks", 104, "Web: industry 2-year date-code convention"),
        ("retest_cost_usd", 1.00, "PLACEHOLDER: re-test/bake per unit past date-code limit"),
        ("rework_accept_rate", 0.80, "PLACEHOLDER: share of route-2 remainder another BU accepts"),
        ("odm_hedge_ratio", 0.0, "PLACEHOLDER: share of claimed MWD the ODM never actually stocked"),
        ("boards_built_ahead_weeks", 2, "PLACEHOLDER (Q10): SMT runs this many weeks ahead of final assembly"),
        ("relocation_weeks", 3, "PLACEHOLDER: old factory -> new factory transit + receiving"),
        ("new_site_lt_adder_weeks", 4, "Practitioner input (virtualized): new SE Asia site, +4 weeks lead time by default"),
        ("relocation_cost_rate", 0.03, "PLACEHOLDER: freight + handling as share of material value; bonded, no duty"),
    ]
    with open(os.path.join(D, "params.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["key", "value", "note"]); w.writerows(params)
    print(f"wrote {len(mats)} materials, {len(rows)} BOM rows, 18 SKUs")

if __name__ == "__main__":
    main()
