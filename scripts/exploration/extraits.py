"""Affiche un extrait autour de chaque mot-clé trouvé, pour relecture.

Usage, depuis le dossier des données :
    python3 ../scripts/exploration/extraits.py passages_senat.csv
    python3 ../scripts/exploration/extraits.py passages_pe.csv Anthropic
Sans filtre : toutes les familles sauf « Entreprises et produits ».
Avec filtres : seulement ces familles ou ces mots-clés.
"""
import csv
import re
import sys

from motscles import FAMILLES, norm

if len(sys.argv) < 2:
    sys.exit(__doc__)
fichier, filtres = sys.argv[1], set(sys.argv[2:])
if not filtres:
    filtres = set(FAMILLES) - {"Entreprises et produits"}

nb = 0
for r in csv.DictReader(open(fichier, encoding="utf-8")):
    for bloc in filter(None, r["mots_cles"].split(" ; ")):
        famille, mots = bloc.split(" : ", 1)
        for mot in mots.split(", "):
            if famille not in filtres and mot not in filtres:
                continue
            rx, mode = FAMILLES[famille][mot]
            texte = r["texte"] if mode.startswith("casse") else norm(r["texte"])
            m = re.search(rx, texte)
            if m:
                nb += 1
                extrait = texte[max(0, m.start() - 250):m.end() + 250]
                print(f"--- {r['date']} | {r['orateur']} | {famille} › {mot}\n…{extrait}…\n")
print(f"{nb} extraits")
