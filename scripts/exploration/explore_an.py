"""Exploration : passages des débats en séance de l'Assemblée nationale qui
parlent d'IA ou contiennent un mot-clé (voir motscles.py)."""
import csv
import glob
import xml.etree.ElementTree as ET
from collections import Counter

from motscles import analyser, decrire

NS = "http://schemas.assemblee-nationale.fr/referentiel"
ns = {"a": NS}
PRESIDENCE = ("Mme la présidente", "M. le président")


def texte(el):
    """Spoken text only: drops the <italique> stage directions (applause…)."""
    parts = [el.text or ""]
    for child in el:
        if child.tag != f"{{{NS}}}italique":
            parts.append(texte(child))
        parts.append(child.tail or "")
    return " ".join(" ".join(parts).split())


def ecrire(nom_fichier, lignes):
    with open(nom_fichier, "w", newline="", encoding="utf-8") as out:
        w = csv.DictWriter(out, fieldnames=list(lignes[0]) if lignes else ["date"])
        w.writeheader()
        w.writerows(lignes)


retenus, par_famille, par_mot, orateurs = [], Counter(), Counter(), Counter()
nb_lus = nb_ia = 0
for f in sorted(glob.glob("an/xml/compteRendu/*.xml")):
    root = ET.parse(f).getroot()
    jour = root.findtext("a:metadonnees/a:dateSeance", namespaces=ns)[:8]
    jour = f"{jour[:4]}-{jour[4:6]}-{jour[6:]}"
    for p in root.iter(f"{{{NS}}}paragraphe"):
        el = p.find("a:texte", ns)
        if el is None:
            continue
        nom = p.findtext("a:orateurs/a:orateur/a:nom", default="", namespaces=ns)
        # The chair is not always flagged roledebat="president": its label too.
        if p.get("roledebat") == "president" or nom in PRESIDENCE:
            continue
        nb_lus += 1
        brut = texte(el)
        parle_ia, familles = analyser(brut)
        if not (parle_ia or familles):
            continue
        nb_ia += parle_ia
        acteur = p.get("id_acteur", "")
        retenus.append({"date": jour, "id_acteur": acteur, "orateur": nom,
                        "parle_ia": "oui" if parle_ia else "non",
                        "mots_cles": decrire(familles), "texte": brut,
                        "id_syceron": p.get("id_syceron"),
                        "fichier": f.split("/")[-1]})
        orateurs[(acteur, nom)] += 1
        for famille, mots in familles.items():
            par_famille[famille] += 1
            par_mot.update(f"{famille} › {m}" for m in mots)

print(f"{nb_lus} paragraphes lus (hors présidence de séance)")
print(f"{len(retenus)} retenus, dont {nb_ia} parlent d'IA explicitement, "
      f"par {len(orateurs)} orateurs différents\n")
print("Par famille de mots-clés (passages) :")
for k, v in par_famille.most_common():
    print(f"  {v:4}  {k}")
print("\nPar mot-clé :")
for k, v in par_mot.most_common():
    print(f"  {v:4}  {k}")
print("\nOrateurs les plus fréquents :")
for (acteur, nom), v in orateurs.most_common(15):
    print(f"  {v:4}  {acteur:10}  {nom}")

ecrire("passages_an.csv", retenus)
print("\nDétail : passages_an.csv")
