"""Exploration : interventions en plénière des eurodéputé·es français·es qui
parlent d'IA ou contiennent un mot-clé (voir motscles.py)."""
import csv
import time
import urllib.parse
import xml.etree.ElementTree as ET
from collections import Counter

from motscles import analyser, decrire
from reseau import lire_json

API = "https://data.europarl.europa.eu/api/v2/speeches"
API_MEPS = "https://data.europarl.europa.eu/api/v2/meps/show-current"
# Server-side searches, French index (it also covers translations). Not only
# « intelligence artificielle »: a speech about ChatGPT alone would never come
# back otherwise. Every result goes through analyser() afterwards, which
# drops the wind called mistral and the like.
RECHERCHES = ["intelligence artificielle", "ChatGPT", "OpenAI", "Mistral",
              "superintelligence", "armes autonomes", "Pause IA"]
PAGE = 50
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def appel(params, adresse=API):
    # Les reprises sont dans reseau : cette API renvoie des 500 passagers, et
    # sans elles le premier échec faisait tomber tout le passage quotidien.
    return lire_json(adresse + "?" + urllib.parse.urlencode(params),
                     {"User-Agent": "PauseIA-veille-exploration"})


def eurodeputes_fr():
    """{European Parliament id: {"nom", "groupe"}} for the French MEPs in
    office, straight from the Parliament's API, so no CRM copy is needed."""
    rep = appel({"country-of-representation": "FR",
                 "format": "application/ld+json"}, API_MEPS)
    return {m["identifier"]: {
                "nom": f"{m.get('givenName', '')} {m.get('familyName', '')}".strip(),
                "groupe": m.get("api:political-group", ""),
            } for m in rep.get("data", [])}


def toutes(texte):
    """{speech id: (metadata, xml text)} for every match, page after page.
    Texts and metadata come in two separate lists whose order differs, so
    they are joined on the id, never on the position."""
    resultats, offset = {}, 0
    while True:
        rep = appel({"text": texte, "search-language": "fr",
                     "parliamentary-term": 10, "sort-by": "sitting-date:desc",
                     "format": "application/ld+json",
                     "include-output": "highlighted_text",
                     "offset": offset, "limit": PAGE})
        donnees = rep.get("data", [])
        total = rep.get("meta", {}).get("total", 0)
        meta = {d["id"]: d for d in donnees}
        avant = len(resultats)
        for h in rep.get("searchResults", {}).get("hits", []):
            resultats[h["id"]] = (meta.get(h["id"]),
                                  h.get("highlights", {}).get("xml_text", ""))
        # Three ways out, so that an API ignoring `offset` cannot loop forever:
        # a short page, the announced total reached, or a page with nothing new.
        if (len(donnees) < PAGE or offset + PAGE >= total
                or len(resultats) == avant):
            return resultats
        offset += PAGE
        time.sleep(0.5)   # well under the 500 requests / 5 min limit


def lire(xml_text):
    """(person id, language, spoken text) from one speech's XML."""
    racine = ET.fromstring(xml_text)
    speech = racine.find(".//speech")
    langue = speech.get(XML_LANG, "") if speech is not None else ""
    personne = racine.find(".//person")
    pid = personne.get("refersTo", "").rsplit("/", 1)[-1] if personne is not None else ""
    corps = racine.find(".//blockContainer")   # the words, without the speaker line
    source = corps if corps is not None else racine
    return pid, langue, " ".join(" ".join(source.itertext()).split())


def ecrire(nom_fichier, lignes):
    with open(nom_fichier, "w", newline="", encoding="utf-8") as out:
        w = csv.DictWriter(out, fieldnames=list(lignes[0]) if lignes else ["date"])
        w.writeheader()
        w.writerows(lignes)


fr = eurodeputes_fr()
print(f"{len(fr)} eurodéputé·es français·es en poste (API du Parlement européen)")
tout = {}
for texte in RECHERCHES:
    r = toutes(texte)
    print(f"  « {texte} » : {len(r)} interventions")
    tout.update(r)
print(f"{len(tout)} interventions distinctes, toutes nationalités\n")

retenus, par_famille, par_mot, orateurs = [], Counter(), Counter(), Counter()
nb_fr = nb_ia = erreurs = 0
for id_, (meta, xml_text) in tout.items():
    try:
        pid, langue, texte = lire(xml_text)
    except ET.ParseError:
        erreurs += 1
        continue
    if pid not in fr:
        continue
    nb_fr += 1
    parle_ia, familles = analyser(texte)
    if not (parle_ia or familles):
        continue
    nb_ia += parle_ia
    origine = ", ".join(
        u.rsplit("/", 1)[-1]
        for r in (meta or {}).get("recorded_in_a_realization_of", [])
        for u in r.get("originalLanguage", []))
    retenus.append({"date": (meta or {}).get("activity_date", ""), "id_pe": pid,
                    "orateur": fr[pid]["nom"], "groupe": fr[pid]["groupe"],
                    "langue": langue, "origine": origine,
                    "parle_ia": "oui" if parle_ia else "non",
                    "mots_cles": decrire(familles), "texte": texte, "id": id_})
    orateurs[(pid, fr[pid]["nom"])] += 1
    for famille, mots in familles.items():
        par_famille[famille] += 1
        par_mot.update(f"{famille} › {m}" for m in mots)

print(f"{nb_fr} interventions d'eurodéputé·es français·es récupérées")
print(f"{len(retenus)} retenues, dont {nb_ia} parlent d'IA explicitement, "
      f"par {len(orateurs)} orateurs différents ; XML illisibles : {erreurs}\n")
print("Par famille de mots-clés (interventions) :")
for k, v in par_famille.most_common():
    print(f"  {v:4}  {k}")
print("\nPar mot-clé :")
for k, v in par_mot.most_common():
    print(f"  {v:4}  {k}")
print("\nQui parle le plus d'IA :")
for (pid, nom), v in orateurs.most_common(15):
    print(f"  {v:4}  {pid:7}  {nom}")

ecrire("passages_pe.csv", retenus)
print("\nDétail : passages_pe.csv")
