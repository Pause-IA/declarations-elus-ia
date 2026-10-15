"""Exploration : questions écrites des député·es (17e législature) qui parlent
d'IA ou contiennent un mot-clé (voir motscles.py)."""
import csv
import json
import re
import zipfile
from collections import Counter
from html import unescape

from motscles import analyser, decrire

# « Mme Olivia Grégoire interroge M. le ministre… »: the file carries only the
# author's id, but every question opens with their name.
AUTEUR = re.compile(r"^(M\.|Mme)\s+(.+?)\s+(interroge|interpelle|attire|appelle"
                    r"|alerte|expose|questionne|souhaite|demande|sollicite"
                    r"|signale|rappelle)")


def premier(x):
    """Converted from XML: one element is a dict, several are a list."""
    if isinstance(x, list):
        return x[0] if x else {}
    return x or {}


def nettoyer(texte):
    """Questions keep a few HTML tags (<em>…) and entities: drop them."""
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", texte or "")).split())


def ecrire(nom_fichier, lignes):
    with open(nom_fichier, "w", newline="", encoding="utf-8") as out:
        w = csv.DictWriter(out, fieldnames=list(lignes[0]) if lignes else ["date"])
        w.writeheader()
        w.writerows(lignes)


z = zipfile.ZipFile("an-questions.zip")
fichiers = [n for n in z.namelist() if n.endswith(".json")]
retenus = []
par_famille, par_mot, auteurs = Counter(), Counter(), Counter()
rubriques, ministeres = Counter(), Counter()
nb_ia = 0
derniere = ""
for nom_fichier in fichiers:
    q = json.loads(z.read(nom_fichier))["question"]
    texte_q = premier((q.get("textesQuestion") or {}).get("texteQuestion"))
    brut = nettoyer(texte_q.get("texte"))
    date = (texte_q.get("infoJO") or {}).get("dateJO") or ""
    derniere = max(derniere, date)
    index = q.get("indexationAN") or {}
    analyse = (index.get("analyses") or {}).get("analyse") or ""
    if isinstance(analyse, list):
        analyse = " ; ".join(analyse)
    # The title is analysed too: « Intelligence artificielle et emploi ».
    parle_ia, familles = analyser(f"{analyse}. {brut}")
    if not (parle_ia or familles):
        continue
    nb_ia += parle_ia
    auteur = q.get("auteur") or {}
    acteur = (auteur.get("identite") or {}).get("acteurRef", "")
    m = AUTEUR.match(brut)
    nom = f"{m.group(1)} {m.group(2)}" if m else ""
    rubrique = index.get("rubrique") or ""
    ministere = (q.get("minInt") or {}).get("abrege") or ""
    retenus.append({"date": date, "id_acteur": acteur, "orateur": nom,
                    "groupe": (auteur.get("groupe") or {}).get("abrege", ""),
                    "rubrique": rubrique, "analyse": analyse,
                    "ministere": ministere,
                    "repondu": "oui" if q.get("textesReponse") else "non",
                    "parle_ia": "oui" if parle_ia else "non",
                    "mots_cles": decrire(familles), "texte": brut,
                    "uid": q.get("uid", "")})
    auteurs[(acteur, nom)] += 1
    rubriques[rubrique] += 1
    ministeres[ministere] += 1
    for famille, mots in familles.items():
        par_famille[famille] += 1
        par_mot.update(f"{famille} › {m}" for m in mots)

print(f"{len(fichiers)} questions écrites lues ; la plus récente date du {derniere}")
print(f"{len(retenus)} retenues, dont {nb_ia} parlent d'IA explicitement, "
      f"par {len(auteurs)} député·es différent·es\n")
print("Par famille de mots-clés (questions) :")
for k, v in par_famille.most_common():
    print(f"  {v:4}  {k}")
print("\nPar mot-clé :")
for k, v in par_mot.most_common():
    print(f"  {v:4}  {k}")
print("\nRubriques des questions retenues :")
for k, v in rubriques.most_common(10):
    print(f"  {v:4}  {k}")
print("\nMinistères interrogés :")
for k, v in ministeres.most_common(8):
    print(f"  {v:4}  {k}")
print("\nDéputé·es qui posent le plus de questions sur le sujet :")
for (acteur, nom), v in auteurs.most_common(15):
    print(f"  {v:4}  {acteur:10}  {nom}")

ecrire("passages_an_questions.csv", retenus)
print("\nDétail : passages_an_questions.csv")
