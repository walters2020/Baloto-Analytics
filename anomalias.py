# -*- coding: utf-8 -*-
import math
from collections import Counter
import pandas as pd
from pathlib import Path as path

file_path = path(__file__).parent / "baloto_resultados.xlsx"
dataset = pd.read_excel(file_path)

def chi_square_uniform(counts, k):
    # counts: dict {item: count}
    n = sum(counts.values())
    expected = n / k
    x2 = sum((counts.get(i, 0) - expected) ** 2 / expected for i in range(1, k + 1))
    return x2

def main():
    # Filtra solo BALOTO
    data = dataset[dataset["juego"] == "BALOTO"].copy()

    # Asegurar orden temporal si tienes sorteo/fecha; si no, al menos por sorteo desc
    if "sorteo" in data.columns:
        data = data.sort_values("sorteo").reset_index(drop=True)
    else:
        data = data.reset_index(drop=True)

    main_counts = Counter()
    sb_counts = Counter()
    pair_counts = Counter()

    # Iterar filas correctamente
    required_cols = ["n1", "n2", "n3", "n4", "n5", "superbalota"]
    missing = [c for c in required_cols if c not in data.columns]
    if missing:
        raise ValueError(f"Faltan columnas en el Excel: {missing}. "
                         f"Columnas encontradas: {list(data.columns)}")

    for row in data.itertuples(index=False):
        main = [int(getattr(row, c)) for c in ["n1", "n2", "n3", "n4", "n5"]]
        sb = int(getattr(row, "superbalota"))

        for x in main:
            main_counts[x] += 1
        sb_counts[sb] += 1

        main_sorted = sorted(main)
        for i in range(5):
            for j in range(i + 1, 5):
                pair_counts[(main_sorted[i], main_sorted[j])] += 1

    x2_main = chi_square_uniform(main_counts, 43)
    x2_sb = chi_square_uniform(sb_counts, 16)

    print("Sorteos BALOTO:", len(data))
    print("Chi-cuadrado principales (43):", x2_main)
    print("Chi-cuadrado superbalota (16):", x2_sb)

    # Ventanas móviles (ej. 120 sorteos)
    W = 120
    step = 20
    if len(data) >= W:
        print("\nVentanas móviles:")
        for start in range(0, len(data) - W + 1, step):
            window = data.iloc[start:start + W]
            c = Counter()
            for row in window.itertuples(index=False):
                main = [int(getattr(row, ccol)) for ccol in ["n1", "n2", "n3", "n4", "n5"]]
                for x in main:
                    c[x] += 1
            x2 = chi_square_uniform(c, 43)
            print(f"  window {start:4d}-{start+W-1:4d}: x2={x2:.2f}")

if __name__ == "__main__":
    main()