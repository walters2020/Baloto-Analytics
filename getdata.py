# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Dict

import pandas as pd
import requests
from bs4 import BeautifulSoup


BASE = "https://www.baloto.com/resultados?page={page}"
SITE = "https://www.baloto.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0 Safari/537.36"
    ),
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
}

TIMEOUT = 30
MAX_PAGES_FALLBACK = 200  # si no logra leer "Página 1 de X"

RE_TOTAL_PAGES = re.compile(r"Página\s+\d+\s+de\s+(\d+)", re.IGNORECASE)
RE_DATE = re.compile(
    r"(\d{1,2}\s+de\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+(?:\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)?\s+de\s+\d{4})",
    re.IGNORECASE,
)
RE_DETAIL = re.compile(r"^/resultados-(baloto|revancha)/(\d{3,6})/?$", re.IGNORECASE)
RE_6_HYPHEN = re.compile(
    r"(\d{1,2}\s*-\s*\d{1,2}\s*-\s*\d{1,2}\s*-\s*\d{1,2}\s*-\s*\d{1,2}\s*-\s*\d{1,2})"
)

@dataclass
class Row:
    juego: str           # BALOTO / REVANCHA
    sorteo: int
    fecha: Optional[str]
    n1: int
    n2: int
    n3: int
    n4: int
    n5: int
    superbalota: int
    page: int
    detail_url: str


def get_soup(session: requests.Session, url: str) -> BeautifulSoup:
    r = session.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def parse_total_pages(soup: BeautifulSoup) -> Optional[int]:
    text = soup.get_text(" ", strip=True)
    m = RE_TOTAL_PAGES.search(text)
    if not m:
        return None
    return int(m.group(1))


def extract_numbers_from_container(container: BeautifulSoup) -> Optional[List[int]]:
    """
    Intento 1: encontrar string "01 - 07 - ... - 05"
    Intento 2: si no hay guiones (por spans), tomar tokens numéricos 1-2 dígitos
               y quedarnos con el último bloque plausible de 6 números
    """
    txt = " ".join(container.stripped_strings)

    # Intento 1: formato con guiones
    m = RE_6_HYPHEN.search(txt)
    if m:
        nums = [int(x) for x in re.findall(r"\d{1,2}", m.group(1))]
        if len(nums) == 6:
            return nums

    # Intento 2: tokens 1-2 dígitos (evita 2026)
    toks = [t.strip() for t in container.stripped_strings]
    small_nums = []
    for t in toks:
        if re.fullmatch(r"\d{1,2}", t):
            small_nums.append(int(t))

    # Heurística: en la fila del histórico deben existir 6 números (5+SB)
    # Nos quedamos con los últimos 6 para evitar capturar el "día" (ej. 2) si aparece suelto.
    if len(small_nums) >= 6:
        cand = small_nums[-6:]
        return cand

    return None


def validate(nums: List[int]) -> bool:
    if len(nums) != 6:
        return False
    main = nums[:5]
    sb = nums[5]
    if len(set(main)) != 5:
        return False
    if not all(1 <= x <= 43 for x in main):
        return False
    if not (1 <= sb <= 16):
        return False
    return True


def parse_page(session: requests.Session, page: int) -> Tuple[List[Row], int]:
    url = BASE.format(page=page)
    soup = get_soup(session, url)

    # Guardar total pages si se encuentra
    total_pages = parse_total_pages(soup) or -1

    rows: List[Row] = []
    seen: set[Tuple[str, int]] = set()

    # Ubica todos los links de "Ver detalle" que apunten a resultados-baloto/revancha
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        m = RE_DETAIL.match(href)
        if not m:
            continue

        juego = m.group(1).upper()
        sorteo = int(m.group(2))
        key = (juego, sorteo)
        if key in seen:
            continue
        seen.add(key)

        detail_url = SITE + href

        # contenedor de la fila (tabla o lista)
        container = a.find_parent("tr") or a.find_parent("li") or a.find_parent("div")
        if container is None:
            continue

        container_text = " ".join(container.stripped_strings)

        # fecha
        fm = RE_DATE.search(container_text)
        fecha = fm.group(1) if fm else None

        nums = extract_numbers_from_container(container)
        if not nums or not validate(nums):
            # Debug: si no pudimos extraer números de esta fila, la saltamos
            continue

        rows.append(Row(
            juego=juego,
            sorteo=sorteo,
            fecha=fecha,
            n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4],
            superbalota=nums[5],
            page=page,
            detail_url=detail_url
        ))

    return rows, total_pages


def main():
    session = requests.Session()
    session.headers.update(HEADERS)

    all_rows: List[Row] = []

    # Página 1 para conocer cuántas páginas hay
    print("Descargando pagina 1...")
    rows1, total = parse_page(session, 1)

    # Si por alguna razón no extrae nada, guarda HTML para inspección
    if len(rows1) == 0:
        html = session.get(BASE.format(page=1), timeout=TIMEOUT).text
        Path("debug_page_1.html").write_text(html, encoding="utf-8")
        raise SystemExit(
            "❌ No se pudo extraer ninguna fila en página 1. "
            "Se guardó debug_page_1.html para inspección (busca '/resultados-baloto/' dentro)."
        )

    all_rows.extend(rows1)
    print(f"   Filas extraidas pag 1: {len(rows1)} | total_pages detectado: {total if total!=-1 else 'N/A'}")

    if total == -1:
        total = MAX_PAGES_FALLBACK

    for page in range(2, total + 1):
        print(f"Descargando pagina {page}...")
        rows, _ = parse_page(session, page)
        print(f"   Filas extraidas: {len(rows)} | acumuladas: {len(all_rows) + len(rows)}")

        # Si una página viene vacía, suele indicar fin real o cambio de formato
        if len(rows) == 0:
            html = session.get(BASE.format(page=page), timeout=TIMEOUT).text
            Path(f"debug_page_{page}.html").write_text(html, encoding="utf-8")
            print(f"Pagina {page} sin filas utiles. Se guardo debug_page_{page}.html. Fin.")
            break

        all_rows.extend(rows)

    df = pd.DataFrame([r.__dict__ for r in all_rows])

    # Orden y deduplicación final
    if not df.empty:
        df = df.drop_duplicates(subset=["juego", "sorteo"]).sort_values(
            ["sorteo", "juego"], ascending=[False, True]
        ).reset_index(drop=True)

    out_path = Path(__file__).parent / "baloto_resultados.xlsx"
    df.to_excel(out_path, index=False)

    print(f"\nGuardado: {out_path}")
    print(f"   Filas: {len(df)} | Sorteos únicos: {df['sorteo'].nunique() if not df.empty else 0}")
    if not df.empty:
        print(df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()