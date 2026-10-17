"""Viabilidad economico-financiera Prevex (USD, 5 anos).

Genera tablas LaTeX y un CSV revisable a partir de supuestos explicitos.
Uso:
  python docs/scripts/viabilidad_negocio.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE.parent / "tables" / "negocio"
OUT_DIR.mkdir(parents=True, exist_ok=True)

K = 0.12  # tasa de descuento real en USD
HORIZON = 5
I0 = 8000.0  # inversion inicial

# Costos unitarios comunes (USD / ano por ART activa), ajustables por escenario.
ASSUMPTIONS = {
    "pesimista": {
        "label": "Pesimista",
        "price_month": 800.0,
        "arts": [1, 1, 1, 1, 1],
        "fixed_opex": 9000.0,
        "var_per_art": 1200.0,
        "cac": 2500.0,
        "historia": "Un solo piloto a precio de entrada; sin escalar; opex fijo alto relativo al ingreso.",
    },
    "base": {
        "label": "Base",
        "price_month": 1200.0,
        "arts": [1, 2, 3, 4, 5],
        "fixed_opex": 11000.0,
        "var_per_art": 1300.0,
        "cac": 2500.0,
        "historia": "Adopcion gradual vía canal de prevencion; precio de referencia.",
    },
    "optimista": {
        "label": "Optimista",
        "price_month": 1500.0,
        "arts": [2, 4, 6, 8, 10],
        "fixed_opex": 12000.0,
        "var_per_art": 1400.0,
        "cac": 3000.0,
        "historia": "Replicacion en varias ART y upsell de precio medio.",
    },
}


def npv(rate: float, cashflows: list[float]) -> float:
    """VAN de flujos en t=0..n (cashflows[0] es ano 0)."""
    return sum(cf / ((1 + rate) ** t) for t, cf in enumerate(cashflows))


def irr(cashflows: list[float], low: float = -0.9, high: float = 5.0) -> float | None:
    """TIR por biseccion; None si no hay cambio de signo."""
    if not (min(cashflows) < 0 < max(cashflows)):
        return None

    def f(r: float) -> float:
        return npv(r, cashflows)

    flo, fhi = f(low), f(high)
    if flo * fhi > 0:
        return None
    for _ in range(80):
        mid = (low + high) / 2
        fm = f(mid)
        if abs(fm) < 1e-8:
            return mid
        if flo * fm < 0:
            high, fhi = mid, fm
        else:
            low, flo = mid, fm
    return (low + high) / 2


def payback_simple(cashflows: list[float]) -> float | None:
    """Anos hasta recuperar (interpolado); None si no recupera."""
    acc = 0.0
    for t, cf in enumerate(cashflows):
        prev = acc
        acc += cf
        if acc >= 0 and t > 0:
            # cruza en este ano
            if cf == 0:
                return float(t)
            return (t - 1) + (-prev) / cf
        if acc >= 0 and t == 0:
            return 0.0
    return None


def payback_discounted(rate: float, cashflows: list[float]) -> float | None:
    disc = [cf / ((1 + rate) ** t) for t, cf in enumerate(cashflows)]
    return payback_simple(disc)


def break_even_arts(fixed_opex: float, price_month: float, var_per_art: float) -> float:
    margin = price_month * 12 - var_per_art
    if margin <= 0:
        return float("inf")
    return fixed_opex / margin


def build_scenario(key: str, cfg: dict) -> dict:
    arts = cfg["arts"]
    price_year = cfg["price_month"] * 12
    rows = []
    prev = 0
    for t in range(1, HORIZON + 1):
        n = arts[t - 1]
        new = max(0, n - prev)
        rev = n * price_year
        opex = cfg["fixed_opex"] + n * cfg["var_per_art"] + new * cfg["cac"]
        net = rev - opex
        rows.append(
            {
                "year": t,
                "arts": n,
                "new_arts": new,
                "revenue": rev,
                "opex": opex,
                "net": net,
            }
        )
        prev = n

    # Ano 0: solo inversion
    cashflows = [-I0] + [r["net"] for r in rows]
    van = npv(K, cashflows)
    tir = irr(cashflows)
    pb = payback_simple(cashflows)
    pbd = payback_discounted(K, cashflows)
    be = break_even_arts(cfg["fixed_opex"], cfg["price_month"], cfg["var_per_art"])

    return {
        "key": key,
        "label": cfg["label"],
        "historia": cfg["historia"],
        "price_month": cfg["price_month"],
        "fixed_opex": cfg["fixed_opex"],
        "var_per_art": cfg["var_per_art"],
        "cac": cfg["cac"],
        "rows": rows,
        "cashflows": cashflows,
        "van": van,
        "tir": tir,
        "payback": pb,
        "payback_disc": pbd,
        "break_even_arts": be,
    }


def fmt_usd(x: float) -> str:
    sign = "-" if x < 0 else ""
    return f"{sign}USD~{abs(x):,.0f}".replace(",", ".")


def fmt_pct(x: float | None) -> str:
    if x is None:
        return "n/d"
    return f"{x * 100:.1f}"


def fmt_years(x: float | None) -> str:
    if x is None:
        return "no recupera en 5 a\\~nos"
    return f"{x:.1f}"


def latex_escape_num(s: str) -> str:
    return s


def write_csv(scenarios: list[dict]) -> None:
    path = OUT_DIR / "flujos_escenarios.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "escenario",
                "ano",
                "arts",
                "nuevas",
                "ingresos_usd",
                "opex_usd",
                "flujo_neto_usd",
            ]
        )
        for sc in scenarios:
            w.writerow([sc["key"], 0, 0, 0, 0, 0, sc["cashflows"][0]])
            for r in sc["rows"]:
                w.writerow(
                    [
                        sc["key"],
                        r["year"],
                        r["arts"],
                        r["new_arts"],
                        round(r["revenue"], 2),
                        round(r["opex"], 2),
                        round(r["net"], 2),
                    ]
                )
    meta = OUT_DIR / "supuestos.json"
    meta.write_text(
        json.dumps(
            {
                "moneda": "USD",
                "horizonte_anos": HORIZON,
                "tasa_descuento": K,
                "inversion_inicial_usd": I0,
                "nota": "Inversion inicial de productizacion comercial.",
                "escenarios": ASSUMPTIONS,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def write_latex(scenarios: list[dict]) -> None:
    # Tabla resumen indicadores
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption[Indicadores de viabilidad por escenario (USD)]{\rev{Indicadores de viabilidad por escenario (USD, $k=12\%$, horizonte 5 a\~nos).} \fuentepropia}",
        r"\label{tab:negocio-indicadores}",
        r"\small",
        r"\begin{tabular}{lrrr}",
        r"\hline",
        r"\textbf{Indicador} & \textbf{Pesimista} & \textbf{Base} & \textbf{Optimista} \\",
        r"\hline",
    ]
    by = {s["key"]: s for s in scenarios}
    p, b, o = by["pesimista"], by["base"], by["optimista"]

    def row(name: str, vals: list[str]) -> str:
        return name + " & " + " & ".join(vals) + r" \\"

    lines.append(
        row(
            "VAN",
            [fmt_usd(p["van"]), fmt_usd(b["van"]), fmt_usd(o["van"])],
        )
    )
    lines.append(
        row(
            "TIR",
            [
                (fmt_pct(p["tir"]) + "\\%") if p["tir"] is not None else "n/d",
                (fmt_pct(b["tir"]) + "\\%") if b["tir"] is not None else "n/d",
                (fmt_pct(o["tir"]) + "\\%") if o["tir"] is not None else "n/d",
            ],
        )
    )
    lines.append(
        row(
            "Payback simple (a\\~nos)",
            [fmt_years(p["payback"]), fmt_years(b["payback"]), fmt_years(o["payback"])],
        )
    )
    lines.append(
        row(
            "Payback descontado (a\\~nos)",
            [
                fmt_years(p["payback_disc"]),
                fmt_years(b["payback_disc"]),
                fmt_years(o["payback_disc"]),
            ],
        )
    )
    lines.append(
        row(
            "Punto de equilibrio (ART)",
            [
                f"{p['break_even_arts']:.1f}",
                f"{b['break_even_arts']:.1f}",
                f"{o['break_even_arts']:.1f}",
            ],
        )
    )
    lines += [
        r"\hline",
        r"\end{tabular}",
        r"\end{table}",
        "",
    ]
    (OUT_DIR / "tab_indicadores.tex").write_text("\n".join(lines), encoding="utf-8")

    # Flujos base (detalle)
    sc = by["base"]
    fl = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption[Flujo de fondos del escenario base (USD)]{\rev{Flujo de fondos del escenario base (USD). A\~no 0 = inversi\'on inicial.} \fuentepropia}",
        r"\label{tab:negocio-flujo-base}",
        r"\small",
        r"\begin{tabular}{rrrrrr}",
        r"\hline",
        r"\textbf{A\~no} & \textbf{ART} & \textbf{Ingresos} & \textbf{Costos} & \textbf{Flujo neto} & \textbf{Acumulado} \\",
        r"\hline",
    ]
    acc = 0.0
    # year 0
    acc += sc["cashflows"][0]
    fl.append(
        f"0 & 0 & {fmt_usd(0)} & {fmt_usd(I0)} & {fmt_usd(sc['cashflows'][0])} & {fmt_usd(acc)} \\\\"
    )
    for r in sc["rows"]:
        acc += r["net"]
        fl.append(
            f"{r['year']} & {r['arts']} & {fmt_usd(r['revenue'])} & {fmt_usd(r['opex'])} "
            f"& {fmt_usd(r['net'])} & {fmt_usd(acc)} \\\\"
        )
    fl += [
        r"\hline",
        r"\end{tabular}",
        r"\end{table}",
        "",
    ]
    (OUT_DIR / "tab_flujo_base.tex").write_text("\n".join(fl), encoding="utf-8")

    # Supuestos
    su = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption[Supuestos de los escenarios (USD)]{\rev{Supuestos de los escenarios (USD).} \fuentepropia}",
        r"\label{tab:negocio-supuestos}",
        r"\small",
        r"\begin{tabular}{lrrr}",
        r"\hline",
        r"\textbf{Supuesto} & \textbf{Pesimista} & \textbf{Base} & \textbf{Optimista} \\",
        r"\hline",
        f"Precio mensual / ART & {fmt_usd(p['price_month'])} & {fmt_usd(b['price_month'])} & {fmt_usd(o['price_month'])} \\\\",
        f"Opex fijo anual & {fmt_usd(p['fixed_opex'])} & {fmt_usd(b['fixed_opex'])} & {fmt_usd(o['fixed_opex'])} \\\\",
        f"Costo variable / ART-ano & {fmt_usd(p['var_per_art'])} & {fmt_usd(b['var_per_art'])} & {fmt_usd(o['var_per_art'])} \\\\",
        f"CAC por ART nueva & {fmt_usd(p['cac'])} & {fmt_usd(b['cac'])} & {fmt_usd(o['cac'])} \\\\",
        f"ART a\\~no 5 & {p['rows'][-1]['arts']} & {b['rows'][-1]['arts']} & {o['rows'][-1]['arts']} \\\\",
        r"\hline",
        r"\end{tabular}",
        r"\end{table}",
        "",
    ]
    (OUT_DIR / "tab_supuestos.tex").write_text("\n".join(su), encoding="utf-8")


def main() -> None:
    scenarios = [build_scenario(k, v) for k, v in ASSUMPTIONS.items()]
    write_csv(scenarios)
    write_latex(scenarios)
    print("Escenarios:")
    for sc in scenarios:
        tir_s = f"{sc['tir']*100:.1f}%" if sc["tir"] is not None else "n/d"
        print(
            f"  {sc['label']}: VAN={sc['van']:.0f} TIR={tir_s} "
            f"PB={sc['payback']} PBd={sc['payback_disc']} BE={sc['break_even_arts']:.2f}"
        )
    print(f"Salida: {OUT_DIR}")


if __name__ == "__main__":
    main()
