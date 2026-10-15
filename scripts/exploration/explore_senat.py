"""Exploration : interventions en séance du Sénat qui parlent d'IA ou
contiennent un mot-clé (voir motscles.py)."""
import csv
import re
import zipfile
from collections import Counter
from datetime import date
from html.parser import HTMLParser

from motscles import analyser, decrire

DEPUIS = "20240701"   # same window as the Assemblée


class Interventions(HTMLParser):
    """Collects (attributes, spoken text) for each <cri:intervenant>.

    The Sénat files are HTML with extra cri: tags, not strict XML, so a
    tolerant HTML parser is used. Speaker labels and stage directions
    (« (Applaudissements…) ») are left out of the text."""
    SAUTER = {"cri:orateurnom", "cri:infoentreparentheses"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.courant, self.morceaux, self.sauter = None, [], 0
        self.resultats = []

    def fermer(self):
        if self.courant is not None:
            texte = " ".join(" ".join(self.morceaux).split())
            if texte:
                self.resultats.append((self.courant, texte))
        self.courant, self.morceaux = None, []

    def handle_starttag(self, tag, attrs):
        if tag == "cri:intervenant":
            self.fermer()
            self.courant = dict(attrs)
        elif tag in self.SAUTER:
            self.sauter += 1

    def handle_endtag(self, tag):
        if tag == "cri:intervenant":
            self.fermer()
        elif tag in self.SAUTER and self.sauter:
            self.sauter -= 1

    def handle_data(self, data):
        if self.courant is not None and not self.sauter:
            self.morceaux.append(data)


def decoder(brut):
    """Files are ISO-8859-1 or UTF-8: use the encoding they declare."""
    m = re.search(rb'encoding="([^"]+)"', brut[:200])
    return brut.decode(m.group(1).decode() if m else "utf-8", "replace")


def ecrire(nom_fichier, lignes):
    with open(nom_fichier, "w", newline="", encoding="utf-8") as out:
        w = csv.DictWriter(out, fieldnames=list(lignes[0]) if lignes else ["date"])
        w.writeheader()
        w.writerows(lignes)


aujourdhui = date.today().strftime("%Y%m%d")
z = zipfile.ZipFile("senat-cri.zip")
fichiers = []
for n in sorted(z.namelist()):
    if not re.fullmatch(r"cri/d\d{8}\.xml", n) or n[5:13] < DEPUIS:
        continue
    # A file named after a future day is a typo (d20261204 = 4 Dec 2025?):
    # never trust it, or it would pass for the most recent sitting.
    if n[5:13] > aujourdhui:
        print(f"⚠ ignoré, daté dans le futur : {n}")
        continue
    fichiers.append(n)

retenus, par_famille, par_mot, orateurs = [], Counter(), Counter(), Counter()
nb_lus = nb_ia = 0
for nom_fichier in fichiers:
    jour = f"{nom_fichier[5:9]}-{nom_fichier[9:11]}-{nom_fichier[11:13]}"
    parser = Interventions()
    parser.feed(decoder(z.read(nom_fichier)))
    parser.fermer()
    for attrs, brut in parser.resultats:
        qualite = attrs.get("qua", "")
        if qualite.startswith("présid") and "séance" in qualite:
            continue  # chairing the sitting, not taking a position
        nb_lus += 1
        parle_ia, familles = analyser(brut)
        if not (parle_ia or familles):
            continue
        nb_ia += parle_ia
        orateur = f"{attrs.get('civ', '')} {attrs.get('nom', '')}".strip()
        matricule = attrs.get("mat", "")
        retenus.append({"date": jour, "matricule": matricule, "orateur": orateur,
                        "qualite": qualite,
                        "parle_ia": "oui" if parle_ia else "non",
                        "mots_cles": decrire(familles), "texte": brut,
                        "fichier": nom_fichier})
        orateurs[(matricule, orateur)] += 1
        for famille, mots in familles.items():
            par_famille[famille] += 1
            par_mot.update(f"{famille} › {m}" for m in mots)

print(f"{len(fichiers)} jours de séance, du {fichiers[0][5:13]} au {fichiers[-1][5:13]}")
print(f"{nb_lus} interventions lues (hors présidence de séance)")
print(f"{len(retenus)} retenues, dont {nb_ia} parlent d'IA explicitement, "
      f"par {len(orateurs)} orateurs différents\n")
print("Par famille de mots-clés (interventions) :")
for k, v in par_famille.most_common():
    print(f"  {v:4}  {k}")
print("\nPar mot-clé :")
for k, v in par_mot.most_common():
    print(f"  {v:4}  {k}")
print("\nOrateurs les plus fréquents :")
for (mat, nom), v in orateurs.most_common(15):
    print(f"  {v:4}  {mat:8}  {nom}")

ecrire("passages_senat.csv", retenus)
print("\nDétail : passages_senat.csv")
