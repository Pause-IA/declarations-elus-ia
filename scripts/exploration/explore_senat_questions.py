"""Exploration : questions des sénateur·ices de l'année écoulée dont le titre
parle d'IA ou contient un mot-clé (voir motscles.py).

The Sénat's CSV carries titles, not texts: this is a first sift, to be
followed by fetching the full text of the questions it keeps."""
import csv
from collections import Counter

from motscles import analyser, decrire


def ecrire(nom_fichier, lignes):
    with open(nom_fichier, "w", newline="", encoding="utf-8") as out:
        w = csv.DictWriter(out, fieldnames=list(lignes[0]) if lignes else ["date"])
        w.writeheader()
        w.writerows(lignes)


# Semicolon-separated, ISO-8859-1: the Sénat's usual encoding.
with open("senat-questions.csv", encoding="iso-8859-1", newline="") as f:
    questions = list(csv.DictReader(f, delimiter=";"))

retenus = []
par_famille, par_mot, auteurs, themes = Counter(), Counter(), Counter(), Counter()
nb_ia = 0
for q in questions:
    titre = q.get("Titre", "")
    parle_ia, familles = analyser(titre)
    if not (parle_ia or familles):
        continue
    nb_ia += parle_ia
    nom = f"{q.get('Civilité', '')} {q.get('Prénom', '')} {q.get('Nom', '')}".strip()
    retenus.append({"date": q.get("Date de publication JO", ""), "orateur": nom,
                    "groupe": q.get("Groupe", ""), "nature": q.get("Nature", ""),
                    "etat": q.get("Sort", ""), "themes": q.get("Thème(s)", ""),
                    "ministere": q.get("Ministère de dépôt", ""),
                    "parle_ia": "oui" if parle_ia else "non",
                    "mots_cles": decrire(familles), "texte": titre,
                    "url": q.get("URL Question", "")})
    auteurs[nom] += 1
    themes[q.get("Thème(s)", "")] += 1
    for famille, mots in familles.items():
        par_famille[famille] += 1
        par_mot.update(f"{famille} › {m}" for m in mots)

dates = sorted(q.get("Date de publication JO", "") for q in questions)
print(f"{len(questions)} questions, du {dates[0]} au {dates[-1]}")
print(f"{len(retenus)} titres retenus, dont {nb_ia} parlent d'IA explicitement, "
      f"par {len(auteurs)} sénateur·ices différent·es\n")
print("Par mot-clé :")
for k, v in par_mot.most_common():
    print(f"  {v:4}  {k}")
print("\nThèmes des questions retenues :")
for k, v in themes.most_common(8):
    print(f"  {v:4}  {k}")
print("\nTitres retenus :")
for r in sorted(retenus, key=lambda r: r["date"], reverse=True):
    print(f"  {r['date']}  {r['orateur']} ({r['groupe']}) : {r['texte']}")

ecrire("passages_senat_questions.csv", retenus)
print("\nDétail : passages_senat_questions.csv")
