"""Lire une adresse en tolérant les pannes passagères de la source.

Écrit après le 19/10/2026 : l'API du Parlement européen a renvoyé « HTTP 500 »
environ une fois sur cinq, de façon intermittente — la même adresse demandée
cinq fois a répondu quatre fois 200 et une fois 500. Trois scripts
l'interrogeaient sans aucune reprise, et le premier échec faisait tomber tout le
passage quotidien. La règle est donc écrite une fois, ici, plutôt que recopiée.

On réessaie sur 5xx, sur 429 et sur une panne réseau, en espaçant les
tentatives. Une erreur 4xx (hors 429) vient de notre requête, pas du serveur :
la réessayer ne servirait à rien, donc elle remonte tout de suite.
"""
import json
import sys
import time
import urllib.error
import urllib.request

ESSAIS = 5
ATTENTES = (3, 8, 20, 45)  # secondes avant chaque nouvelle tentative
AGENT = "PauseIA-veille"


def ouvrir(adresse, entetes=None, timeout=60, essais=ESSAIS):
    """Le corps de la réponse, en octets. b"" si la source répond « sans contenu ».

    `essais` : nombre de tentatives (ESSAIS par défaut). Moins quand on sonde
    une page déjà connue pour échouer, pour ne pas attendre une minute et demie
    à chaque morceau.

    « 204 No Content » n'est pas une erreur : c'est ce que répond l'API quand on
    demande une page au-delà de la dernière. L'appelant le lit comme une fin de
    liste.
    """
    requete = urllib.request.Request(
        adresse, headers=entetes or {"User-Agent": AGENT})
    for tentative in range(essais):
        try:
            with urllib.request.urlopen(requete, timeout=timeout) as reponse:
                return b"" if reponse.status == 204 else reponse.read()
        except urllib.error.HTTPError as err:
            if not (err.code >= 500 or err.code == 429) or tentative == essais - 1:
                raise
            motif = f"HTTP {err.code}"
        except (urllib.error.URLError, TimeoutError) as err:
            if tentative == essais - 1:
                raise
            motif = f"{type(err).__name__}: {err}"
        attente = ATTENTES[min(tentative, len(ATTENTES) - 1)]
        print(f"  … {motif}, nouvelle tentative dans {attente} s",
              file=sys.stderr, flush=True)
        time.sleep(attente)


def lire_json(adresse, entetes=None, timeout=60, essais=ESSAIS):
    """Le JSON d'une adresse. {} si la réponse est vide (fin de liste)."""
    corps = ouvrir(adresse, entetes, timeout, essais)
    return json.loads(corps) if corps.strip() else {}


def lire_texte(adresse, entetes=None, timeout=60, encodage="utf-8"):
    """Le texte d'une adresse, les octets illisibles remplacés plutôt que levés."""
    return ouvrir(adresse, entetes, timeout).decode(encodage, "replace")
