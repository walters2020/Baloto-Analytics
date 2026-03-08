# -*- coding: utf-8 -*-
"""
Análisis Baloto (patrón de "orden" por posiciones, gaps, rango/paridad)
+ números calientes/fríos + pares/ternas frecuentes + mezcla hot/cold.

Lee un Excel local:
    file_path = Path(__file__).parent / "baloto_resultados.xlsx"
    dataset = pd.read_excel(file_path)

Requisitos:
    pip install pandas openpyxl
"""

from __future__ import annotations

import itertools
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# =========================
# Helpers
# =========================

def _norm(s: str) -> str:
    """Normaliza nombres de columna: minúsculas, sin tildes, sin espacios raros."""
    s = str(s).strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace(" ", "_").replace("-", "_")
    s = "".join(ch for ch in s if ch.isalnum() or ch == "_")
    return s


def _quantiles(series: pd.Series) -> Dict[str, float]:
    return {
        "min": float(series.min()),
        "p25": float(series.quantile(0.25)),
        "median": float(series.median()),
        "mean": float(series.mean()),
        "p75": float(series.quantile(0.75)),
        "max": float(series.max()),
    }


@dataclass
class Cols:
    date: Optional[str]
    game: Optional[str]
    n: List[str]   # 5 columnas (n1..n5)
    sb: str        # superbalota


def detect_columns(df: pd.DataFrame) -> Cols:
    """
    Detecta columnas en tu Excel de forma robusta.
    Espera encontrar:
      - fecha (opcional)
      - juego/tipo (opcional: para filtrar Baloto vs Revancha)
      - 5 números principales
      - superbalota
    """
    original_cols = list(df.columns)
    norm_map = {c: _norm(c) for c in original_cols}
    inv = {}
    for orig, nm in norm_map.items():
        inv.setdefault(nm, []).append(orig)

    norm_cols = set(norm_map.values())

    # fecha
    date_candidates = [c for c in norm_cols if c in {"fecha", "date", "draw_date", "fecha_sorteo"} or c.startswith("fecha")]
    date_col = inv[date_candidates[0]][0] if date_candidates else None

    # juego/tipo
    game_candidates = [c for c in norm_cols if c in {"juego", "tipo", "producto", "modalidad"}]
    game_col = inv[game_candidates[0]][0] if game_candidates else None

    # superbalota
    sb_candidates = [c for c in norm_cols if c in {"sb", "super", "superbalota", "super_balota", "super_b"}]
    if not sb_candidates:
        # heurística: contiene "super" y "balota"
        sb_candidates = [c for c in norm_cols if ("super" in c and "balota" in c)]
    if not sb_candidates:
        raise ValueError("No pude detectar la columna de SúperBalota (sb/super/superbalota).")

    sb_col = inv[sb_candidates[0]][0]

    # 5 números principales:
    # Caso ideal: n1..n5
    n_cols = []
    for k in range(1, 6):
        for key in (f"n{k}", f"num{k}", f"numero{k}", f"baloto_{k}", f"baloto{k}", f"bola{k}"):
            if key in norm_cols:
                n_cols.append(inv[key][0])
                break

    # Si no se detectaron así, intentar: columnas numéricas "parecidas"
    if len(n_cols) != 5:
        # Busca columnas cuyo nombre normalizado termine en _1.._5
        maybe = []
        for nm in norm_cols:
            for k in range(1, 6):
                if nm.endswith(f"_{k}") or nm.endswith(str(k)):
                    if any(tok in nm for tok in ["n", "num", "numero", "baloto", "bola"]):
                        maybe.append((k, inv[nm][0]))
        maybe_sorted = [col for _, col in sorted(maybe, key=lambda x: x[0])]
        # quita duplicados preservando orden
        seen = set()
        maybe_sorted = [x for x in maybe_sorted if not (x in seen or seen.add(x))]
        if len(maybe_sorted) >= 5:
            n_cols = maybe_sorted[:5]

    if len(n_cols) != 5:
        raise ValueError(
            "No pude detectar las 5 columnas principales (n1..n5). "
            "Asegúrate de tener columnas tipo: n1,n2,n3,n4,n5 (o num1..num5)."
        )

    return Cols(date=date_col, game=game_col, n=n_cols, sb=sb_col)


def prepare_baloto(df: pd.DataFrame, cols: Cols) -> pd.DataFrame:
    """Limpia, tipa y deja un DF listo: fecha, n1..n5, sb (solo Baloto si aplica)."""
    work = df.copy()

    # normaliza nombres internos
    rename = {}
    if cols.date:
        rename[cols.date] = "fecha"
    if cols.game:
        rename[cols.game] = "juego"
    for i, c in enumerate(cols.n, start=1):
        rename[c] = f"n{i}"
    rename[cols.sb] = "sb"

    work = work.rename(columns=rename)

    # filtrar Baloto si hay columna de juego
    if "juego" in work.columns:
        work["juego_norm"] = work["juego"].astype(str).str.lower()
        work = work[work["juego_norm"].str.contains("baloto", na=False)].copy()

    # tipos numéricos
    for c in ["n1", "n2", "n3", "n4", "n5", "sb"]:
        work[c] = pd.to_numeric(work[c], errors="coerce").astype("Int64")

    # fecha
    if "fecha" in work.columns:
        work["fecha"] = pd.to_datetime(work["fecha"], errors="coerce").dt.date

    # drop filas inválidas
    work = work.dropna(subset=["n1", "n2", "n3", "n4", "n5", "sb"]).copy()

    # asegurar enteros "normales"
    for c in ["n1", "n2", "n3", "n4", "n5", "sb"]:
        work[c] = work[c].astype(int)

    # ordenar n1..n5 por si el Excel no está ordenado (aquí el "patrón de orden" es por posiciones)
    main = work[["n1", "n2", "n3", "n4", "n5"]].to_numpy()
    main_sorted = np.sort(main, axis=1)
    work[["n1", "n2", "n3", "n4", "n5"]] = main_sorted

    # ordenar por fecha desc si existe
    if "fecha" in work.columns:
        work = work.sort_values("fecha", ascending=False).reset_index(drop=True)
    else:
        work = work.reset_index(drop=True)

    return work


# =========================
# Análisis
# =========================

def analyze_order_pattern(df: pd.DataFrame, last_n: int = 100) -> Dict[str, object]:
    """
    "Patrón de orden" por posiciones (n1..n5) + gaps + rango/suma + consecutivos + paridad
    sobre los últimos N sorteos.
    """
    d = df.head(last_n).copy()

    # stats por posición
    pos_stats = {c: _quantiles(d[c]) for c in ["n1", "n2", "n3", "n4", "n5"]}

    # gaps
    d["g1"] = d["n2"] - d["n1"]
    d["g2"] = d["n3"] - d["n2"]
    d["g3"] = d["n4"] - d["n3"]
    d["g4"] = d["n5"] - d["n4"]
    gap_cols = ["g1", "g2", "g3", "g4"]

    gap_stats = {}
    for g in gap_cols:
        s = d[g]
        gap_stats[g] = {
            "min": int(s.min()),
            "median": float(s.median()),
            "mean": float(s.mean()),
            "max": int(s.max()),
            "pct_le_2": float((s <= 2).mean()),
            "pct_eq_1": float((s == 1).mean()),
        }

    # rango/suma
    d["range"] = d["n5"] - d["n1"]
    d["sum"] = d[["n1", "n2", "n3", "n4", "n5"]].sum(axis=1)

    # consecutivos y gaps "pequeños"
    d["has_consecutive"] = (d[gap_cols] == 1).any(axis=1)
    d["has_gap_le2"] = (d[gap_cols] <= 2).any(axis=1)
    d["num_consecutive_pairs"] = (d[gap_cols] == 1).sum(axis=1)
    d["max_gap"] = d[gap_cols].max(axis=1)

    summary = {
        "pct_draws_with_consecutive": float(d["has_consecutive"].mean()),
        "pct_draws_with_gap_le2": float(d["has_gap_le2"].mean()),
        "avg_consecutive_pairs": float(d["num_consecutive_pairs"].mean()),
        "pct_draws_with_2_or_more_consecutive_pairs": float((d["num_consecutive_pairs"] >= 2).mean()),
        "pct_draws_max_gap_ge15": float((d["max_gap"] >= 15).mean()),
        "range_stats": _quantiles(d["range"]),
        "sum_stats": _quantiles(d["sum"]),
    }

    # paridad
    main_cols = ["n1", "n2", "n3", "n4", "n5"]
    d["evens"] = d[main_cols].apply(lambda r: sum(int(x % 2 == 0) for x in r), axis=1)
    even_dist = d["evens"].value_counts().sort_index()
    even_dist_pct = (even_dist / len(d)).round(4)

    return {
        "window_rows": len(d),
        "pos_stats": pos_stats,
        "gap_stats": gap_stats,
        "summary": summary,
        "even_dist_counts": even_dist.to_dict(),
        "even_dist_pct": even_dist_pct.to_dict(),
    }


def analyze_hot_cold_and_combos(
    df: pd.DataFrame,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    top_k: int = 10,
) -> Dict[str, object]:
    """
    Números calientes/fríos (top/bottom K) + superbalota + pares/ternas frecuentes + mezcla hot/cold.
    Si el DF trae columna fecha, puedes acotar rango con start_date/end_date (YYYY-MM-DD).
    """
    d = df.copy()
    if "fecha" in d.columns and (start_date or end_date):
        if start_date:
            sd = pd.to_datetime(start_date).date()
            d = d[d["fecha"] >= sd]
        if end_date:
            ed = pd.to_datetime(end_date).date()
            d = d[d["fecha"] <= ed]
        d = d.copy()

    # frecuencias main
    main_nums = d[["n1", "n2", "n3", "n4", "n5"]].to_numpy().ravel()
    main_counts = Counter(map(int, main_nums))
    main_freq = (
        pd.DataFrame([{"num": n, "count": c} for n, c in main_counts.items()])
        .sort_values(["count", "num"], ascending=[False, True])
        .reset_index(drop=True)
    )

    hot = main_freq.head(top_k)
    cold = main_freq.sort_values(["count", "num"], ascending=[True, True]).head(top_k)
    hot_set = set(hot["num"].tolist())
    cold_set = set(cold["num"].tolist())

    # superbalota
    sb_counts = Counter(map(int, d["sb"].tolist()))
    sb_freq = (
        pd.DataFrame([{"sb": k, "count": v} for k, v in sb_counts.items()])
        .sort_values(["count", "sb"], ascending=[False, True])
        .reset_index(drop=True)
    )
    sb_hot = sb_freq.head(min(top_k, len(sb_freq)))
    sb_cold = sb_freq.sort_values(["count", "sb"], ascending=[True, True]).head(min(top_k, len(sb_freq)))

    # pares / ternas
    pairs = Counter()
    triples = Counter()
    for row in d[["n1", "n2", "n3", "n4", "n5"]].itertuples(index=False, name=None):
        row = tuple(map(int, row))
        for p in itertools.combinations(row, 2):
            pairs[p] += 1
        for t in itertools.combinations(row, 3):
            triples[t] += 1

    top_pairs = [(a, b, c) for (a, b), c in pairs.most_common(15)]
    top_triples = [(t, c) for (t, c) in triples.most_common(10)]

    # pares hot-hot, cold-cold, hot-cold
    hot_hot = sorted(
        [((a, b), c) for (a, b), c in pairs.items() if a in hot_set and b in hot_set],
        key=lambda x: (-x[1], x[0]),
    )[:10]
    cold_cold = sorted(
        [((a, b), c) for (a, b), c in pairs.items() if a in cold_set and b in cold_set],
        key=lambda x: (-x[1], x[0]),
    )[:10]
    hot_cold = sorted(
        [((a, b), c) for (a, b), c in pairs.items() if (a in hot_set and b in cold_set) or (a in cold_set and b in hot_set)],
        key=lambda x: (-x[1], x[0]),
    )[:10]

    # mezcla por sorteo: hot_count / cold_count
    def _hc_counts(row: Tuple[int, int, int, int, int]) -> Tuple[int, int]:
        h = sum(1 for x in row if x in hot_set)
        c = sum(1 for x in row if x in cold_set)
        return h, c

    hc = d[["n1", "n2", "n3", "n4", "n5"]].apply(lambda r: _hc_counts(tuple(map(int, r))), axis=1)
    hc_df = pd.DataFrame(hc.tolist(), columns=["hot_count", "cold_count"])
    mix = (
        hc_df.groupby(["hot_count", "cold_count"]).size().reset_index(name="draws")
        .sort_values("draws", ascending=False)
        .reset_index(drop=True)
    )

    return {
        "rows": len(d),
        "hot": hot,
        "cold": cold,
        "sb_hot": sb_hot,
        "sb_cold": sb_cold,
        "top_pairs": top_pairs,
        "top_triples": top_triples,
        "hot_hot_pairs": [((a, b), c) for ((a, b), c) in hot_hot],
        "cold_cold_pairs": [((a, b), c) for ((a, b), c) in cold_cold],
        "hot_cold_pairs": [((a, b), c) for ((a, b), c) in hot_cold],
        "mix_table": mix,
    }


# =========================
# Pretty print
# =========================

def print_order_results(res: Dict[str, object]) -> None:
    print("\n==============================")
    print(f"ANÁLISIS PATRÓN (últimos {res['window_rows']} sorteos)")
    print("==============================")

    print("\n[Posiciones n1..n5] (min, p25, mediana, media, p75, max)")
    for k, stats in res["pos_stats"].items():
        print(f"  {k}: {stats}")

    print("\n[Gaps g1..g4]")
    for g, stats in res["gap_stats"].items():
        print(f"  {g}: {stats}")

    print("\n[Resumen]")
    for k, v in res["summary"].items():
        print(f"  {k}: {v}")

    print("\n[Paridad: #pares en los 5 números]")
    print("  counts:", res["even_dist_counts"])
    print("  pct   :", res["even_dist_pct"])


def print_hotcold_results(res: Dict[str, object]) -> None:
    print("\n==============================")
    print(f"HOT/COLD + COMBINACIONES (rows={res['rows']})")
    print("==============================")

    print("\n[Hot (Top)]")
    print(res["hot"].to_string(index=False))

    print("\n[Cold (Bottom)]")
    print(res["cold"].to_string(index=False))

    print("\n[SúperBalota Hot]")
    print(res["sb_hot"].to_string(index=False))

    print("\n[SúperBalota Cold]")
    print(res["sb_cold"].to_string(index=False))

    print("\n[Top pares (a,b,count)]")
    for a, b, c in res["top_pairs"]:
        print(f"  ({a:02d},{b:02d}) -> {c}")

    print("\n[Top ternas (tuple,count)]")
    for t, c in res["top_triples"]:
        print(f"  {t} -> {c}")

    print("\n[Pares Hot-Hot más frecuentes]")
    for (a, b), c in res["hot_hot_pairs"]:
        print(f"  ({a:02d},{b:02d}) -> {c}")

    print("\n[Pares Cold-Cold más frecuentes]")
    for (a, b), c in res["cold_cold_pairs"]:
        print(f"  ({a:02d},{b:02d}) -> {c}")

    print("\n[Pares Hot-Cold más frecuentes]")
    for (a, b), c in res["hot_cold_pairs"]:
        print(f"  ({a:02d},{b:02d}) -> {c}")

    print("\n[Mezcla Hot/Cold por sorteo] (hot_count, cold_count -> draws)")
    print(res["mix_table"].head(12).to_string(index=False))


# =========================
# Main
# =========================

def main() -> None:
    # --- Carga
    file_path = Path(__file__).parent / "baloto_resultados.xlsx"
    dataset = pd.read_excel(file_path)

    cols = detect_columns(dataset)
    df = prepare_baloto(dataset, cols)

    if len(df) < 20:
        raise ValueError(f"Dataset muy pequeño después de limpiar/filtrar: {len(df)} filas.")

    # --- 1) Patrón de orden (últimos 100)
    order_res = analyze_order_pattern(df, last_n=100)
    print_order_results(order_res)

    # --- 2) Hot/Cold + combinaciones (toda la historia del Excel)
    hc_res = analyze_hot_cold_and_combos(df, top_k=10)
    print_hotcold_results(hc_res)

    # --- 3) (Opcional) Hot/Cold por año, si tienes fecha
    if "fecha" in df.columns and df["fecha"].notna().any():
        years = sorted({d.year for d in df["fecha"] if pd.notna(d)})
        for y in years[-3:]:  # últimos 3 años disponibles
            sub = df[df["fecha"].apply(lambda x: x.year if pd.notna(x) else None) == y]
            if len(sub) < 10:
                continue
            print("\n------------------------------")
            print(f"HOT/COLD por año: {y} (rows={len(sub)})")
            print("------------------------------")
            year_res = analyze_hot_cold_and_combos(sub, top_k=10)
            print("[Hot]")
            print(year_res["hot"].to_string(index=False))
            print("[Cold]")
            print(year_res["cold"].to_string(index=False))
            print("[SB Hot]")
            print(year_res["sb_hot"].to_string(index=False))

    # --- 4) Exportar a Excel
    out = Path(__file__).parent / "baloto_analisis_output.xlsx"
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        pd.DataFrame(order_res["pos_stats"]).T.to_excel(w, sheet_name="order_pos_stats")
        pd.DataFrame(order_res["gap_stats"]).T.to_excel(w, sheet_name="order_gap_stats")
        pd.DataFrame([order_res["summary"]]).T.to_excel(w, sheet_name="order_summary")
        hc_res["hot"].to_excel(w, sheet_name="hot", index=False)
        hc_res["cold"].to_excel(w, sheet_name="cold", index=False)
        hc_res["sb_hot"].to_excel(w, sheet_name="sb_hot", index=False)
        hc_res["sb_cold"].to_excel(w, sheet_name="sb_cold", index=False)
        pd.DataFrame(hc_res["top_pairs"], columns=["a","b","count"]).to_excel(w, sheet_name="top_pairs", index=False)
        pd.DataFrame([(tuple(t),c) for (t,c) in hc_res["top_triples"]], columns=["triple","count"]).to_excel(w, sheet_name="top_triples", index=False)
        hc_res["mix_table"].to_excel(w, sheet_name="mix_hot_cold", index=False)
    print(f"\n[OK] Exportado: {out}")

if __name__ == "__main__":
    main()