"""Questions écrites récentes des eurodéputé·es français·es, par l'API du Parlement.

Complète explore_pe_questions.py (Parltrack, arrêté à la mi-juillet 2026).
La liste de l'API ne donne que les identifiants : l'auteur, la date et le titre
sont dans la fiche de chaque question. On lit donc les fiches de la plus récente
à la plus ancienne, et on s'arrête quand on passe avant la date de début.
Chaque fiche lue est gardée en cache : elle n'est jamais redemandée.
robots.txt demande 2 s entre deux requêtes.

Usage : python3 explore_pe_questions_api.py [AAAA-MM-JJ]
"""
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import date

from motscles import analyser, decrire

API = "https://data.europarl.europa.eu/api/v2"
ELI = "https://data.europarl.europa.eu/eli/dl/doc/"
DEPUIS = sys.argv[1] if len(sys.argv) > 1 else "2026-07-16"  # lendemain de Parltrack
TYPES = ("QUESTION_WRITTEN", "QUESTION_WRITTEN_PRIORITY")
PAR_PAGE = 100
PAUSE = 2             # Crawl-delay de robots.txt
ARRET = 30            # fiches plus anciennes que DEPUIS d'affilée avant d'arrêter
ESSAIS = 5            # tentatives par requête : l'API renvoie des 500 passagers
ATTENTES = (3, 8, 20, 45)  # secondes avant chaque nouvelle tentative
INCOMPLET = []        # (année, type) dont la liste n'a pas pu être lue en entier
CACHE = "pe_questions_fiches.json"
SORTIE = "passages_pe_questions_recentes.csv"
SIGLE_AI = re.compile(r"(?<![\w-])AI(?![\w-])")


def lire_json(adresse):
    """Lit une adresse de l'API, en réessayant tant que l'erreur est passagère.

    Le 19/10/2026 l'API a renvoyé « HTTP Error 500 » environ une fois sur cinq,
    de façon intermittente : la même adresse demandée cinq fois de suite a
    répondu quatre fois 200 et une fois 500. Sans reprise, un passage qui
    enchaîne une quinzaine de requêtes de structure n'avait donc presque aucune
    chance d'aboutir, et il échouait en entier.

    On réessaie sur 5xx, sur 429 et sur une panne réseau, en espaçant les
    tentatives. Une erreur 4xx (hors 429) vient de notre requête, pas du
    serveur : la réessayer ne servirait à rien, donc elle remonte tout de suite.

    « 204 No Content » n'est pas une erreur : c'est la réponse de l'API quand on
    demande une page au-delà de la dernière. Le corps est vide, donc json.load
    y levait une exception. On rend une réponse vide, que l'appelant lit comme
    une fin de liste.
    """
    requete = urllib.request.Request(adresse, headers={
        "User-Agent": "PauseIA-veille", "Accept": "application/ld+json"})
    for tentative in range(ESSAIS):
        try:
            with urllib.request.urlopen(requete, timeout=60) as reponse:
                if reponse.status == 204:
                    return {}
                corps = reponse.read()
                return json.loads(corps) if corps.strip() else {}
        except urllib.error.HTTPError as err:
            passagere = err.code >= 500 or err.code == 429
            if not passagere or tentative == ESSAIS - 1:
                raise
            motif = f"HTTP {err.code}"
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as err:
            if tentative == ESSAIS - 1:
                raise
            motif = f"{type(err).__name__}: {err}"
        attente = ATTENTES[min(tentative, len(ATTENTES) - 1)]
        print(f"  … {motif}, nouvelle tentative dans {attente} s",
              file=sys.stderr, flush=True)
        time.sleep(attente)


def eurodeputes_fr():
    """{identifiant: (nom, groupe)} pour les élu·es français·es en poste."""
    resultat = {}
    for m in lire_json(f"{API}/meps/show-current?format=application%2Fld%2Bjson"
                       "&offset=0&limit=1000")["data"]:
        if m.get("api:country-of-representation") == "FR":
            ident = str(m.get("identifier") or m["id"].split("/")[-1])
            resultat[ident] = (m.get("label", ""), m.get("api:political-group", ""))
    return resultat


def identifiants(annee, type_q):
    """Tous les identifiants d'une année et d'un type, page par page.

    Si une page reste en échec après toutes les tentatives, on rend ce qu'on a
    déjà et on retient l'année dans INCOMPLET : les identifiants manquants
    seront lus au passage suivant, puisque le cache ne garde que les fiches
    réussies. Mieux vaut une liste partielle qu'aucune donnée du tout.
    """
    tous, offset = [], 0
    while True:
        try:
            page = lire_json(f"{API}/parliamentary-questions?year={annee}&work-type={type_q}"
                             f"&format=application%2Fld%2Bjson&offset={offset}"
                             f"&limit={PAR_PAGE}").get("data", [])
        except (OSError, ValueError) as err:
            print(f"  ✗ {annee} {type_q} à l'offset {offset} : {err} — "
                  f"liste partielle ({len(tous)} identifiants)",
                  file=sys.stderr, flush=True)
            INCOMPLET.append((annee, type_q))
            return tous
        tous += [q.get("identifier") or q["id"].split("/")[-1] for q in page]
        print(f"  {annee} {type_q} : {len(tous)} identifiants…", flush=True)
        time.sleep(PAUSE)
        if len(page) < PAR_PAGE:
            return tous
        offset += PAR_PAGE


def fiche(identifiant):
    """{date, auteurs, titre} d'une question (titre en français, sinon en anglais)."""
    d = lire_json(ELI + identifiant)["data"][0]
    titres = d.get("title_dcterms", {})
    return {
        "date": d.get("document_date", "")[:10],
        "auteurs": [c.split("/")[-1] for c in d.get("creator", [])],
        "titre": titres.get("fr") or titres.get("en") or next(iter(titres.values()), ""),
    }


def sauver(cache):
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


def main():
    elus = eurodeputes_fr()
    print(len(elus), "eurodéputé·es français·es")
    cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}

    # 1. Les fiches pas encore lues, de la plus récente à la plus ancienne
    lues = 0
    for annee in range(date.today().year, int(DEPUIS[:4]) - 1, -1):
        for type_q in TYPES:
            anciennes = 0
            for identifiant in sorted(identifiants(annee, type_q), reverse=True):
                if identifiant not in cache:
                    try:
                        cache[identifiant] = fiche(identifiant)
                    except (OSError, ValueError, KeyError, IndexError) as err:
                        print(f"  ✗ {identifiant} : {err}")  # on passe à la suivante
                        continue
                    lues += 1
                    if lues % 50 == 0:
                        sauver(cache)
                        print(f"  {lues} fiches lues (on en est au {cache[identifiant]['date']})")
                    time.sleep(PAUSE)
                # Les identifiants suivent à peu près l'ordre des dates
                anciennes = anciennes + 1 if cache[identifiant]["date"] < DEPUIS else 0
                if anciennes >= ARRET:
                    break
    sauver(cache)
    print(f"{lues} nouvelles fiches lues, {len(cache)} en cache")

    # 2. Analyse des titres des élu·es français·es, une ligne par auteur·ice
    lignes = []
    for identifiant, q in cache.items():
        francais = [a for a in q["auteurs"] if a in elus]
        if not francais or q["date"] < DEPUIS or not q["titre"]:
            continue
        parle_ia, familles = analyser(SIGLE_AI.sub("artificial intelligence", q["titre"]))
        if not parle_ia and not familles:
            continue
        for a in francais:
            nom, groupe = elus[a]
            lignes.append({
                "date": q["date"], "id_acteur": a, "orateur": nom, "groupe": groupe,
                "parle_ia": parle_ia, "mots_cles": decrire(familles), "texte": q["titre"],
                "reference": identifiant,
                "url": f"https://www.europarl.europa.eu/doceo/document/{identifiant}_FR.html",
            })
    lignes.sort(key=lambda l: l["date"], reverse=True)

    with open(SORTIE, "w", newline="", encoding="utf-8") as f:
        ecrivain = csv.DictWriter(f, fieldnames=list(lignes[0]) if lignes else ["date"])
        ecrivain.writeheader()
        ecrivain.writerows(lignes)

    auteurs = Counter(l["orateur"] for l in lignes)
    print(f"{len(lignes)} lignes retenues depuis le {DEPUIS}, par {len(auteurs)} eurodéputé·es")
    for l in lignes[:30]:
        print(f"  {l['date']}  {l['orateur']} : {l['texte']}")
    print(f"\nDétail : {SORTIE}")

    # Le fichier est écrit et le cache sauvé : la synthèse peut travailler. Mais
    # on sort en erreur pour que le passage se signale, sinon une source qui se
    # dégrade s'installerait sans que personne le sache.
    if INCOMPLET:
        manquantes = ", ".join(f"{a} {t}" for a, t in INCOMPLET)
        raise SystemExit(f"Listes incomplètes ({manquantes}) : "
                         f"l'API a échoué après {ESSAIS} tentatives.")


if __name__ == "__main__":
    main()