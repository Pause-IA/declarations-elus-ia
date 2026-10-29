"""Synthèse : une ligne par élu·e, toutes sources confondues.

Lit les passages_*.csv produits par les scripts d'exploration et écrit
synthese_elus.csv (séparateur « ; », s'ouvre directement dans Excel).
"""
import csv
import os
import re
import json
import sys
import hashlib
from datetime import date
from collections import defaultdict

from motscles import IA, analyser, norm, position, occurrences, sans_titre

# (fichier, chambre, type) ; les fichiers absents sont simplement ignorés
SOURCES = [
    ("passages_an.csv", "Assemblée nationale", "séance"),
    ("passages_an_questions.csv", "Assemblée nationale", "question écrite"),
    ("passages_senat.csv", "Sénat", "séance"),
    ("passages_senat_questions_complet.csv", "Sénat", "question écrite"),
    ("passages_pe.csv", "Parlement européen", "séance"),
    ("passages_pe_questions.csv", "Parlement européen", "question écrite"),
    ("passages_pe_questions_recentes.csv", "Parlement européen", "question écrite"),
]
SECOURS = {"passages_senat_questions_complet.csv": "passages_senat_questions.csv"}

# Poids d'un passage = poids de la famille la plus forte qu'il contient
POIDS = {
    "Risques extrêmes": 10,
    "Organisations de la sécurité de l'IA": 8,
    "Sécurité et gouvernance de l'IA": 5,
    "Personnalités": 4,
    "Entreprises et produits": 1,
}
ORDRE = list(POIDS)

# Ajustements par mot-clé, quand le signal est plus faible que sa famille
POIDS_MOTS = {
    "contrôle humain": 2,  # formule courante sur l'IA dans l'administration
    "Arthur Mensch": 1,    # cité comme patron de Mistral, pas pour les risques
    "Sam Altman": 2,
    "Yann LeCun": 1,       # plutôt sceptique sur les risques
}


# Repérage automatique : qualité à l'AN, type d'intervenant au Sénat
# (1 = sénateur·ice, 2 = gouvernement, autre = invité·e extérieur·e)
RE_GOUV = re.compile(r"ministre|secr[ée]taire d.[ée]tat|garde des sceaux"
                     r"|porte-parole du gouvernement", re.I)


def categorie(row, chambre):
    if row.get("type") == "2" or RE_GOUV.search(row.get("qualite", "")):
        return "Gouvernement"
    if row.get("id_acteur", "").startswith("PA-") or row.get("type") not in (None, "", "1"):
        return "Personnalités auditionnées"
    return chambre


SIGLE_AI = re.compile(r"(?<![\w-])AI(?![\w-])")
CIVILITE = re.compile(r"^(m\.|mme|monsieur|madame)\s+", re.I)
PARENTHESE = re.compile(r"\s*\(.*?\)\s*$")
SORTIE = "synthese_elus.csv"
SORTIE_JSON = "synthese_elus.json"
DEJA_VUS = "deja_vus.json"  # mémoire : date de première apparition de chaque passage
SEUIL_ALERTE = 4  # poids minimal d'un passage pour déclencher une alerte
GROUPES_AN = "deputes_datan.csv"   # Datan (data.gouv.fr) : député·es en exercice
GROUPES_SENAT = "senateurs.csv"    # Sénat : ODSEN_GENERAL, en ISO-8859-1


def nettoyer_nom(nom):
    """« M. Alexandre BASQUIN (CRCE-K) » -> « Alexandre Basquin »."""
    nom = PARENTHESE.sub("", CIVILITE.sub("", nom.strip())).strip()
    return " ".join(m.title() if m.isupper() and len(m) > 1 else m for m in nom.split())


def cle(nom):
    """Clé de regroupement insensible aux accents, à la casse et aux tirets."""
    return re.sub(r"[\s-]+", " ", norm(nettoyer_nom(nom))).strip()


def extrait(texte, familles, taille=450):
    """(morceau centré sur le mot-clé le plus fort, [[début, fin] à mettre en gras])."""
    debut = None
    candidats = sorted(((POIDS_MOTS.get(m, POIDS.get(f, 0)), f, m)
                        for f, mots in familles.items() for m in mots), reverse=True)
    for _, f, m in candidats:
        debut = position(texte, f, m)
        if debut is not None:
            break
    if debut is None:
        m = re.search(IA, sans_titre(norm(texte)))
        debut = m.start() if m else 0
    debut = max(0, debut - 200)
    fin = min(len(texte), debut + taille)
    prefixe = "…" if debut else ""
    morceau = prefixe + texte[debut:fin] + ("…" if fin < len(texte) else "")

    # Positions des mots-clés, ramenées au début du morceau
    decalage = debut - len(prefixe)
    marques = []
    for f, mots in familles.items():
        for mot in mots:
            for d, e in occurrences(texte, f, mot):
                if d >= debut and e <= fin:
                    marques.append([d - decalage, e - decalage])
    marques.sort()
    fusion = []
    for d, e in marques:  # deux mots-clés qui se chevauchent : une seule zone
        if fusion and d <= fusion[-1][1]:
            fusion[-1][1] = max(fusion[-1][1], e)
        else:
            fusion.append([d, e])
    return morceau, fusion


def charger_groupes():
    """{identifiant officiel: groupe} : PA… pour l'AN, matricule pour le Sénat."""
    groupes = {}
    if os.path.exists(GROUPES_AN):
        with open(GROUPES_AN, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                groupes[r["id"]] = r["groupeAbrev"]
    if os.path.exists(GROUPES_SENAT):
        with open(GROUPES_SENAT, encoding="iso-8859-1", newline="") as f:
            lignes = (ligne for ligne in f if not ligne.startswith("%"))
            for r in csv.DictReader(lignes):
                groupes[r["Matricule"]] = r["Groupe politique"]
    print(f"Groupes : {len(groupes)} parlementaires connus")
    return groupes


def lire(fichier):
    if not os.path.exists(fichier) and fichier in SECOURS:
        fichier = SECOURS[fichier]
    if not os.path.exists(fichier):
        print(f"  (absent : {fichier})")
        return []
    with open(fichier, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    groupes = charger_groupes()
    elus = {}
    citations = defaultdict(set)  # personnalité -> élu·es qui la citent
    aujourdhui = date.today().isoformat()
    premier_lancement = not os.path.exists(DEJA_VUS)
    vus = {} if premier_lancement else json.load(open(DEJA_VUS, encoding="utf-8"))
    for fichier, chambre, type_ in SOURCES:
        lignes = lire(fichier)
        print(f"  {len(lignes):5}  {fichier}")
        for row in lignes:
            nom = row.get("orateur", "")
            if not nom:
                continue
            if len(nom) > 60:
                print(f"  ⚠ nom suspect ignoré ({fichier}) : {nom[:80]}…")
                continue
            texte = " ".join(filter(None, [row.get("titre"), row.get("analyse"), row.get("texte")]))
            parle_ia, familles = analyser(SIGLE_AI.sub("artificial intelligence", texte))
            if not parle_ia and not familles:
                continue
            ch = categorie(row, chambre)
            k = (ch, cle(nom))
            e = elus.setdefault(k, {
                "nom": nettoyer_nom(nom), "chambre": ch, "groupe": "",
                "passages": set(), "types": set(), "mots": defaultdict(set),
                "dates": [], "score": 0, "meilleur": (-1, "", "", ""),
                "liste":[], "ids": set(),
            })
            empreinte = (row.get("date", ""), texte[:200])
            if empreinte in e["passages"]:
                continue  # même passage lu deux fois
            e["passages"].add(empreinte)
            e["types"].add(type_)
            officiel = row.get("id_acteur") or row.get("matricule") or row.get("id_pe") or ""
            if officiel:
                # PA… (AN), matricule (Sénat), numéro (PE) : de quoi relier
                # l'élu·e à sa fiche dans le CRM sans se fier au seul nom.
                e["ids"].add(officiel)
            if ch != "Gouvernement":  # un ministre ne siège plus dans un groupe
                e["groupe"] = e["groupe"] or row.get("groupe", "") or groupes.get(officiel, "")
            e["dates"].append(row.get("date", ""))
            for famille, mots in familles.items():
                e["mots"][famille].update(mots)
            for mot in familles.get("Personnalités", []):
                citations[mot].add(e["nom"])

            poids = max((POIDS_MOTS.get(mot, POIDS.get(f, 0))
                         for f, mots in familles.items() for mot in mots), default=0)
            e["score"] += poids
            morceau, marques = extrait(texte, familles)
            candidat = (poids, row.get("date", ""), morceau, row.get("url", ""))
            if candidat[:2] > e["meilleur"][:2]:
                e["meilleur"] = candidat
            identifiant = hashlib.sha1(f"{k}|{empreinte}".encode()).hexdigest()[:16]
            vu_le = vus.setdefault(identifiant, "" if premier_lancement else aujourdhui)
            e["liste"].append({
                "date": row.get("date", ""), "type": type_, "poids": poids,
                "mots": {f: sorted(m) for f, m in familles.items()},
                "extrait": morceau, "marques": marques, "lien": row.get("url", ""),
                "vu_le": vu_le,
            })
    if not elus:
        print(f"⚠ Aucun passage trouvé dans {os.getcwd()} : rien n'est écrit.\n"
              "  Lancez la synthèse depuis le dossier des données (donnees-veille).")
        sys.exit(1)
    # Score final : poids des mots-clés + 1 point par passage IA (plafonné à 10)
    for e in elus.values():
        e["score"] += min(len(e["passages"]), 10)

    classement = sorted(elus.values(), key=lambda e: (-e["score"], e["nom"]))
    with open(DEJA_VUS, "w", encoding="utf-8") as f:
        json.dump(vus, f)
    nouveaux = sum(1 for v in vus.values() if v == aujourdhui)
    print(f"Mémoire : {len(vus)} passages connus, dont {nouveaux} vus pour la première fois aujourd'hui")
    with open(SORTIE, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["score", "nom", "chambre", "groupe", "passages IA", "types",
                    *ORDRE, "première date", "dernière date",
                    "extrait le plus pertinent", "lien"])
        for e in classement:
            dates = sorted(d for d in e["dates"] if d)
            w.writerow([
                e["score"], e["nom"], e["chambre"], e["groupe"], len(e["passages"]),
                ", ".join(sorted(e["types"])),
                *[", ".join(sorted(e["mots"].get(f, []))) for f in ORDRE],
                dates[0] if dates else "", dates[-1] if dates else "",
                e["meilleur"][2], e["meilleur"][3],
            ])
    personnes = []
    for e in classement:
        dates = sorted(d for d in e["dates"] if d)
        personnes.append({
            "nom": e["nom"], "chambre": e["chambre"], "groupe": e["groupe"],
            "ids_officiels": sorted(e["ids"]),
            "score": e["score"], "nb_passages": len(e["passages"]),
            "types": sorted(e["types"]),
            "mots": {f: sorted(e["mots"][f]) for f in ORDRE if e["mots"].get(f)},
            "premiere_date": dates[0] if dates else "",
            "derniere_date": dates[-1] if dates else "",
            "nouveau_le": max((p["vu_le"] for p in e["liste"] if p["poids"] >= SEUIL_ALERTE),
                              default=""),
            "passages": sorted(e["liste"], key=lambda p: (p["poids"], p["date"]), reverse=True),
        })
    with open(SORTIE_JSON, "w", encoding="utf-8") as f:
        json.dump({"genere_le": date.today().isoformat(), "poids": POIDS,
                   "poids_mots": POIDS_MOTS, "seuil_alerte": SEUIL_ALERTE, "personnes": personnes},
                  f, ensure_ascii=False, indent=1)

    alertes = [p["nom"] for p in personnes if p["nouveau_le"] == aujourdhui]
    print(f"🔔 {len(alertes)} alerte(s) aujourd'hui : {', '.join(alertes)}")

    print(f"\n{len(classement)} personnes au total")
    for chambre in ("Assemblée nationale", "Sénat", "Parlement européen",
                    "Gouvernement", "Personnalités auditionnées"):
        print(f"  {sum(e['chambre'] == chambre for e in classement):4}  {chambre}")
    chambres_par_nom = defaultdict(set)
    for (ch, k) in elus:
        chambres_par_nom[k].add(ch)
    doublons = [k for k, chs in chambres_par_nom.items() if len(chs) > 1]
    if doublons:
        print("\nOnt changé de rôle (élu·e ↔ gouvernement), à vérifier si doute :", ", ".join(sorted(doublons)))
    print("\nTop 40 :")
    for e in classement[:40]:
        fortes = [f"{f} : {', '.join(sorted(e['mots'][f]))}"
                  for f in ORDRE[:4] if e["mots"].get(f)]
        print(f"  {e['score']:4}  {e['nom']} ({e['chambre']}, {len(e['passages'])} passages)")
        for ligne in fortes:
            print(f"          {ligne}")

    if citations:
        print("\nPersonnalités citées, et par qui :")
        for mot, noms in sorted(citations.items(), key=lambda x: -len(x[1])):
            print(f"  {mot} : {', '.join(sorted(noms))}")

    print(f"\nFichier pour l'équipe plaidoyer : {SORTIE}")


if __name__ == "__main__":
    main()