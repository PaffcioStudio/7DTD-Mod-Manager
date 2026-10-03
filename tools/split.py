#!/usr/bin/env python3
"""Dzieli obraz złożony z dwóch obrazków (góra/dół) na dwa osobne pliki.

Zamiast ciąć ślepo w połowie, skrypt wykrywa szew między obrazkami
(pas, w którym gwałtownie zmienia się jasność wierszy) i tnie dokładnie
po jego obu stronach, dzięki czemu w wynikach nie zostaje ani piksel
rozmytego łączenia. Domyślnie oba wyniki mają identyczną wysokość.
"""
import argparse
import os
import sys

# Ustalanie ścieżek względem lokalizacji skryptu (./tools/split.py -> ../.venv)
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, ".."))
venv_dir = os.path.join(project_root, ".venv")
venv_python = os.path.join(venv_dir, "bin", "python3")

# 1. Sprawdzenie czy istnieje ../.venv
if not os.path.exists(venv_python):
    print(f"Błąd: Nie znaleziono środowiska wirtualnego w: {venv_dir}")
    print("Utwórz je najpierw (np. przez ./venv.sh).")
    sys.exit(1)

# 2. Przełączenie na Pythona z ../.venv, jeśli skrypt uruchomiono systemowym python3
if os.path.abspath(sys.prefix) != os.path.abspath(venv_dir):
    os.execv(venv_python, [venv_python] + sys.argv)

# 3. Sprawdzenie czy Pillow jest zainstalowany w .venv
try:
    from PIL import Image, ImageOps
except ImportError:
    print("Błąd: Biblioteka Pillow nie jest zainstalowana w środowisku .venv.")
    print(f"Zainstaluj ją poleceniem: {venv_python} -m pip install Pillow")
    sys.exit(1)

# Zakres poszukiwań szwu (ułamek wysokości obrazu) i próg pewności wykrycia
ZAKRES_SZUKANIA = (0.30, 0.70)
MIN_SKOK_JASNOSCI = 8.0     # poniżej tego uznajemy, że szwu nie ma
PROG_STREFY = 0.10          # wiersz należy do szwu, gdy skok > 10% skoku maksymalnego


def srednie_wierszy(img):
    """Średnia jasność każdego wiersza (bez numpy: skalowanie do 1 px szerokości)."""
    kolumna = img.convert("L").resize((1, img.height), Image.Resampling.BOX)
    if hasattr(kolumna, "get_flattened_data"):
        return list(kolumna.get_flattened_data())
    return list(kolumna.getdata())


def znajdz_szew(img):
    """Zwraca (koniec_gory, poczatek_dolu, opis).

    Góra to wiersze [0, koniec_gory), dół to [poczatek_dolu, wysokosc).
    Gdy szwu nie da się pewnie wykryć, wraca do cięcia w połowie.
    """
    h = img.height
    polowa = h // 2
    m = srednie_wierszy(img)
    skok = [0.0] + [abs(m[y] - m[y - 1]) for y in range(1, h)]

    lo = max(1, int(h * ZAKRES_SZUKANIA[0]))
    hi = min(h - 1, int(h * ZAKRES_SZUKANIA[1]))
    szczyt = max(range(lo, hi), key=lambda y: skok[y])

    if skok[szczyt] < MIN_SKOK_JASNOSCI:
        return polowa, polowa, "brak wyraźnego szwu, cięcie w połowie"

    prog = skok[szczyt] * PROG_STREFY
    start = szczyt
    while start - 1 > 0 and skok[start - 1] > prog:
        start -= 1
    koniec = szczyt
    while koniec + 1 < h and skok[koniec + 1] > prog:
        koniec += 1

    # skok[y] opisuje przejście między wierszem y-1 a y:
    # góra kończy się przed wierszem 'start', dół zaczyna się po wierszu 'koniec'
    return start, koniec + 1, f"wykryto szew w wierszach {start}-{koniec}"


def zapisz(img, sciezka, exif, icc):
    ext = os.path.splitext(sciezka)[1].lower()
    opcje = {}
    if icc:
        opcje["icc_profile"] = icc
    if ext in (".jpg", ".jpeg"):
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        opcje.update(quality=95, subsampling=0, optimize=True)
        if exif:
            opcje["exif"] = exif
    elif ext == ".png":
        opcje.update(optimize=True)
    elif ext == ".webp":
        opcje.update(lossless=True, quality=100)
    img.save(sciezka, **opcje)


def przetworz(input_path, output_dir, args):
    with Image.open(input_path) as src:
        exif = src.info.get("exif")
        icc = src.info.get("icc_profile")
        img = ImageOps.exif_transpose(src)
        img.load()

    szerokosc, wysokosc = img.size
    if wysokosc < 4:
        print(f"Błąd: Obraz '{input_path}' jest zbyt niski, aby go podzielić.")
        return False

    if args.linia is not None:
        if not 1 <= args.linia < wysokosc:
            print(f"Błąd: --linia musi być w zakresie 1-{wysokosc - 1}.")
            return False
        gora_do, dol_od, opis = args.linia, args.linia, f"ręczna linia cięcia: {args.linia}"
    elif args.polowa:
        gora_do = dol_od = wysokosc // 2
        opis = "cięcie w połowie (wymuszone)"
    else:
        gora_do, dol_od, opis = znajdz_szew(img)

    # Dodatkowy margines bezpieczeństwa po obu stronach szwu
    gora_do -= args.margines
    dol_od += args.margines

    gora_h = gora_do
    dol_h = wysokosc - dol_od
    if gora_h < 1 or dol_h < 1:
        print("Błąd: Po uwzględnieniu marginesu któryś z obrazków ma zerową wysokość.")
        return False

    gora_od = 0
    dol_do = wysokosc

    # Wyrównanie wysokości: obcinamy nadmiar od strony szwu, bo tam
    # najłatwiej o pozostałości łączenia, a krawędzie zewnętrzne zostają nietknięte
    if not args.bez_wyrownania:
        docelowa = min(gora_h, dol_h)
        gora_od = gora_do - docelowa
        dol_do = dol_od + docelowa

    top_img = img.crop((0, gora_od, szerokosc, gora_do))
    bottom_img = img.crop((0, dol_od, szerokosc, dol_do))

    nazwa, ext = os.path.splitext(os.path.basename(input_path))
    top_path = os.path.join(output_dir, f"{nazwa}_gora{ext}")
    bottom_path = os.path.join(output_dir, f"{nazwa}_dol{ext}")

    zapisz(top_img, top_path, exif, icc)
    zapisz(bottom_img, bottom_path, exif, icc)

    print(f"{input_path}: {opis}")
    print(f"  wejście: {szerokosc}x{wysokosc}")
    print(f"  góra: {top_img.width}x{top_img.height} (wiersze {gora_od}-{gora_do - 1}) -> {top_path}")
    print(f"  dół:  {bottom_img.width}x{bottom_img.height} (wiersze {dol_od}-{dol_do - 1}) -> {bottom_path}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Dzieli obraz na górny i dolny obrazek, wykrywając szew automatycznie."
    )
    parser.add_argument("pliki", nargs="+", metavar="ścieżka_do_pliku")
    parser.add_argument("--linia", type=int, metavar="Y",
                        help="ręcznie wskaż wiersz cięcia zamiast autodetekcji")
    parser.add_argument("--polowa", action="store_true",
                        help="wymuś cięcie dokładnie w połowie wysokości")
    parser.add_argument("--margines", type=int, default=0, metavar="PX",
                        help="dodatkowe piksele odcinane po obu stronach szwu (domyślnie 0)")
    parser.add_argument("--bez-wyrownania", action="store_true",
                        help="nie wyrównuj wysokości obu obrazków")
    args = parser.parse_args()

    if args.margines < 0:
        print("Błąd: --margines nie może być ujemny.")
        sys.exit(1)

    # Zapis zawsze wewnątrz folderu ze skryptem (./tools/output)
    output_dir = os.path.join(script_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    wszystko_ok = True
    for sciezka in args.pliki:
        if not os.path.isfile(sciezka):
            print(f"Błąd: Plik '{sciezka}' nie istnieje.")
            wszystko_ok = False
            continue
        try:
            wszystko_ok &= przetworz(sciezka, output_dir, args)
        except OSError as e:
            print(f"Błąd: Nie udało się przetworzyć '{sciezka}': {e}")
            wszystko_ok = False

    sys.exit(0 if wszystko_ok else 1)


if __name__ == "__main__":
    main()
