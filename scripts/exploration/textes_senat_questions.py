"""Récupère sur senat.fr le texte complet des questions retenues par
explore_senat_questions.py (le CSV du Sénat ne donne que les titres), puis
les repasse dans analyser() avec les mots-clés de motscles.py."""
import csv
import re
import time
import urllib.request
from collections import Counter
from html import unescape

from motscles import analyser, decrire

# « Question de M. BASQUIN Alexandre (Nord - CRCE-K) publiée le 08/10/2026 »
# opens the text, « Publiée dans le JO Sénat » closes it.
QUESTION = re.compile(r"Question de (?:M\.|Mme) .+? publiée le \d{2}/\d{2}/\d{4} "
                      r"(.+?) Publiée dans le JO Sénat")


def page_en_texte(url):
    req = urllib.request.Request(url, headers={"User-Agent": "PauseIA-veille-exploration"})
    html = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    debut, fin = html.find("<main"), html.find("</main>")
    zone = html[debut:fin] if debut >= 0 else html     # the page body, no menus
    zone = re.sub(r"<(script|style)\b.*?</\1>", " ", zone, flags=re.S)
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", zone)).split())


def ecrire(nom_fichier, lignes):
    with open(nom_fichier, "w", newline="", encoding="utf-8") as out:
        w = csv.DictWriter(out, fieldnames=list(lignes[0]) if lignes else ["date"])
        w.writeheader()
        w.writerows(lignes)


lignes = list(csv.DictReader(open("passages_senat_questions.csv", encoding="utf-8")))
complets, par_mot, introuvables = [], Counter(), []
for i, r in enumerate(lignes, 1):
    print(f"  {i}/{len(lignes)} {r['url']}", flush=True)
    try:
        m = QUESTION.search(page_en_texte(r["url"]))
    except OSError as e:          # network error: note it and move on
        introuvables.append(f"{r['url']} ({e})")
        continue
    if not m:
        introuvables.append(r["url"])
        continue
    texte = m.group(1)
    parle_ia, familles = analyser(f"{r['texte']}. {texte}")   # title + text
    complets.append({**r, "titre": r["texte"], "texte": texte,
                     "parle_ia": "oui" if parle_ia else "non",
                     "mots_cles": decrire(familles)})
    for famille, mots in familles.items():
        par_mot.update(f"{famille} › {mot}" for mot in mots)
    time.sleep(1)                 # one page a second: be gentle with senat.fr

print(f"\n{len(complets)} textes récupérés, {len(introuvables)} introuvables")
for u in introuvables:
    print("  introuvable :", u)
print("\nPar mot-clé (titre + texte complet) :")
for k, v in par_mot.most_common():
    print(f"  {v:4}  {k}")

ecrire("passages_senat_questions_complet.csv", complets)
print("\nDétail : passages_senat_questions_complet.csv")
