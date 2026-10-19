"""Questions écrites des eurodéputé·es français·es (législature 10).

Source : dump Parltrack (parltrack-activities.json, décompressé du .zst),
car l'API du Parlement ne donne pas les titres et les pages doceo sont
interdites aux robots. Seul le titre (en anglais) est disponible.
"""
import csv
import json
import re
from collections import Counter

from motscles import analyser, decrire
from reseau import lire_json

API_MEPS = ("https://data.europarl.europa.eu/api/v2/meps/show-current"
            "?format=application%2Fld%2Bjson&offset=0&limit=1000")
DUMP = "parltrack-activities.json"
SORTIE = "passages_pe_questions.csv"

# « AI » en majuscules = sigle anglais ; on le traduit pour que motscles le voie
SIGLE_AI = re.compile(r"(?<![\w-])AI(?![\w-])")


def eurodeputes_fr():
    """Renvoie {identifiant: (nom, groupe)} pour les élu·es français·es."""
    donnees = lire_json(API_MEPS)["data"]   # reprises : voir reseau.py
    resultat = {}
    for m in donnees:
        if m.get("api:country-of-representation") != "FR":
            continue
        identifiant = str(m.get("identifier") or m["id"].split("/")[-1])
        resultat[identifiant] = (m.get("label", ""), m.get("api:political-group", ""))
    return resultat


def main():
    elus = eurodeputes_fr()
    print(len(elus), "eurodéputé·es français·es")

    with open(DUMP, encoding="utf-8") as f:
        deputes = json.load(f)

    lignes, total, plus_recente = [], 0, ""
    for d in deputes:
        identifiant = str(d.get("mep_id"))
        if identifiant not in elus:
            continue
        nom, groupe = elus[identifiant]
        for q in d.get("WQ", []):
            if q.get("term") != 10:
                continue
            total += 1
            date = q.get("date", "")[:10]
            plus_recente = max(plus_recente, date)
            titre = q.get("title", "")
            parle_ia, familles = analyser(SIGLE_AI.sub("artificial intelligence", titre))
            if not parle_ia and not familles:
                continue
            lignes.append({
                "date": date, "id_acteur": identifiant, "orateur": nom,
                "groupe": groupe, "parle_ia": parle_ia,
                "mots_cles": decrire(familles), "texte": titre,
                "reference": q.get("reference", ""), "url": q.get("url", ""),
            })

    lignes.sort(key=lambda l: l["date"], reverse=True)
    with open(SORTIE, "w", newline="", encoding="utf-8") as f:
        ecrivain = csv.DictWriter(f, fieldnames=list(lignes[0]) if lignes else ["date"])
        ecrivain.writeheader()
        ecrivain.writerows(lignes)

    auteurs = Counter(l["orateur"] for l in lignes)
    print(f"{total} questions écrites lues ; la plus récente date du {plus_recente}")
    print(f"{len(lignes)} retenues, par {len(auteurs)} eurodéputé·es différent·es\n")
    print("Qui en pose le plus :")
    for nom, n in auteurs.most_common(15):
        print(f"  {n:4}  {nom}")
    print("\nTitres retenus :")
    for l in lignes:
        mots = f"  [{l['mots_cles']}]" if l["mots_cles"] else ""
        print(f"  {l['date']}  {l['orateur']} : {l['texte']}{mots}")
    print(f"\nDétail : {SORTIE}")


if __name__ == "__main__":
    main()