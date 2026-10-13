"""
Three scenarios that exercise the MWD rules.

A  Temporary cut  : Brazil plans for P1-14 cancelled for the whole 16-week window; Brazil demand returns later.
B  Factory transfer: US production leaves this (China) factory now. P1 collective EOL at week 30.
C  Transfer near EOL: same as B, but P1 collective EOL pulled in to week 20 and P2 NPI at week 16.
C0 = C under the old v0 rule (netting only beyond purchase lead time) — kept for comparison.
D  Transfer very late: US leaves only 8 weeks before P1 collective EOL (P2 NPI at week 4).
"""
import os
import mwd_engine as E

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")

SCENARIOS = [
    {"name": "A_temporary_cut_BR",
     "cancel": lambda s: s == "P1-14_BR", "cancel_weeks": 16, "future_gone": False},
    {"name": "B_transfer_US_eol30",
     "cancel": lambda s: s.endswith("_US"), "cancel_weeks": 16, "future_gone": True},
    {"name": "C0_eol20_old_rule",
     "cancel": lambda s: s.endswith("_US"), "cancel_weeks": 16, "future_gone": True,
     "netting_rule": "lead_time",
     "overrides": {"platform_eol": {"P1": 20}, "npi_week": {"P2-14": 16}}},
    {"name": "C_transfer_US_eol20",
     "cancel": lambda s: s.endswith("_US"), "cancel_weeks": 16, "future_gone": True,
     "overrides": {"platform_eol": {"P1": 20}, "npi_week": {"P2-14": 16}}},
    {"name": "D_transfer_US_eol8",
     "cancel": lambda s: s.endswith("_US"), "cancel_weeks": 16, "future_gone": True,
     "overrides": {"platform_eol": {"P1": 8}, "npi_week": {"P2-14": 4}}},
]

def fmt(x): return f"{x:>12,.0f}"

def main():
    os.makedirs(OUT, exist_ok=True)
    data = E.load()
    print(f"{'scenario':<22}{'freed $':>12}{'holding $':>12}{'ageing $':>12}"
          f"{'rework $':>12}{'MWD $':>12}{' of which C1':>12}{'C2':>10}{'C3':>12}")
    for sc in SCENARIOS:
        rows = E.run_event(sc, data)
        E.write_rows(rows, os.path.join(OUT, f"{sc['name']}.csv"))
        s = E.summarize(rows)
        print(f"{sc['name']:<22}{fmt(s['freed_usd'])}{fmt(s['holding_usd'])}{fmt(s['ageing_usd'])}"
              f"{fmt(s['rework_usd'])}{fmt(s['mwd_claimed_usd'])}{fmt(s['mwd_class1_usd'])}"
              f"{s['mwd_class2_usd']:>10,.0f}{fmt(s['mwd_class3_usd'])}")

if __name__ == "__main__":
    main()
