#!/usr/bin/env python3
"""Servir la page de veille, et laisser déposer ses fichiers sans accès serveur.

La page et ses données sont produites par les scripts de ce dépôt, sur la
machine de qui les lance. Il faut donc un endroit où les poser pour que
l'équipe plaidoyer les consulte — et ce dépôt doit se faire depuis un
navigateur, sinon chaque mise à jour passe par quelqu'un qui a les accès au
serveur, et cette personne devient le goulot d'étranglement.

Deux choses seulement :

- la page est servie derrière un mot de passe. Elle affiche un classement
  nommatif d'élu·es et porte la mention « à ne pas diffuser » : elle ne peut
  pas être en accès libre ;
- `/deposer` accepte les deux fichiers, depuis le navigateur ou depuis un
  script (jeton), et refuse un fichier abîmé AVANT de remplacer celui qui
  marche.

Application séparée du CRM, délibérément : elle évolue vite, elle appartient à
ce projet, et son JavaScript ne tourne pas sur l'origine du CRM — donc il ne
peut rien lire des fiches ni des courriels. On rapprochera les deux quand la
veille aura fait ses preuves.
"""
import json
import os
import secrets
import urllib.error
import urllib.request
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)

ICI = Path(__file__).resolve().parent
RACINE = ICI.parent

# Les fichiers déposés vivent dans un volume, hors de l'image : ils survivent
# aux reconstructions, contrairement à tout ce que le Dockerfile copie.
DONNEES = Path(os.environ.get("VEILLE_DATA_DIR", "/data"))
# La page livrée avec l'image sert tant que personne n'en a déposé une autre :
# un déploiement neuf affiche donc déjà quelque chose, et il ne reste qu'à
# déposer le JSON.
PAGE_PAR_DEFAUT = RACINE / "page" / "index.html"

FICHIERS = ("index.html", "synthese_elus.json")
TAILLE_MAX = 32 * 1024 * 1024

MOT_DE_PASSE = os.environ.get("VEILLE_PASSWORD", "")
JETON = os.environ.get("VEILLE_UPLOAD_TOKEN", "")

# Recharger la page depuis le dépôt, pour que celui-ci reste la seule
# référence. Sans ça il y a deux copies d'`index.html` — celle du dépôt et
# celle déposée — et c'est la déposée qui s'affiche : on modifie la page, on
# pousse, et rien ne change en ligne sans comprendre pourquoi.
#
# L'adresse est construite à partir de la CONFIGURATION, jamais de ce que
# l'utilisateurice envoie. Un champ « URL à charger » ferait de ce service un
# moyen d'aller frapper n'importe quelle machine depuis l'intérieur du réseau.
DEPOT = os.environ.get("VEILLE_DEPOT", "Pause-IA/declarations-elus-ia")
BRANCHE = os.environ.get("VEILLE_BRANCHE", "main")
CHEMIN_PAGE = "page/index.html"
# Seulement si le dépôt passe en privé un jour.
JETON_GITHUB = os.environ.get("VEILLE_GITHUB_TOKEN", "")


def url_page_depot():
    return (f"https://raw.githubusercontent.com/{DEPOT}/{BRANCHE}/{CHEMIN_PAGE}")


def lire_page_depot():
    """Le contenu de `page/index.html` sur le dépôt, ou une exception."""
    requete = urllib.request.Request(
        url_page_depot(), headers={"User-Agent": "veille-elus-ia"})
    if JETON_GITHUB:
        requete.add_header("Authorization", f"Bearer {JETON_GITHUB}")
    with urllib.request.urlopen(requete, timeout=30) as reponse:
        return reponse.read(TAILLE_MAX + 1)

app = Flask(__name__)
# Sans clé fixée, les sessions ne survivent pas à un redémarrage : on se
# reconnecte, rien de plus. Mieux vaut ça qu'une clé en dur dans le dépôt.
app.secret_key = os.environ.get("VEILLE_SECRET_KEY") or secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = TAILLE_MAX + 1024


def connexion_requise(vue):
    @wraps(vue)
    def enveloppe(*args, **kwargs):
        if not session.get("ok"):
            return redirect(url_for("connexion", suite=request.path))
        return vue(*args, **kwargs)

    return enveloppe


def valide(nom, contenu):
    """(ok, pourquoi) — un fichier abîmé ne doit jamais remplacer le bon.

    Un dépôt interrompu ou un JSON tronqué remplacerait une page qui marche par
    une page vide, et personne ne saurait pourquoi.
    """
    if not contenu:
        return False, "fichier vide"
    if len(contenu) > TAILLE_MAX:
        return False, f"fichier trop gros ({len(contenu)} octets)"
    if nom == "synthese_elus.json":
        try:
            donnees = json.loads(contenu.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            return False, f"JSON illisible : {exc}"
        if not isinstance(donnees, dict):
            return False, "le JSON attendu est un objet"
        manquantes = [c for c in ("personnes", "genere_le") if c not in donnees]
        if manquantes:
            return False, "clés manquantes : " + ", ".join(manquantes)
        if not isinstance(donnees["personnes"], list) or not donnees["personnes"]:
            return False, "aucune personne dans le fichier"
    elif b"<" not in contenu[:4096]:
        return False, "ne ressemble pas à une page HTML"
    return True, ""


def ecrire(nom, contenu):
    """Remplacer sans jamais servir un fichier à moitié écrit.

    On écrit à côté puis on renomme — `os.replace` est atomique — et la version
    précédente reste en `.bak`, pour qu'un mauvais dépôt se défasse d'une
    commande plutôt que d'un nouvel export.
    """
    DONNEES.mkdir(parents=True, exist_ok=True)
    cible = DONNEES / nom
    provisoire = DONNEES / (nom + ".tmp")
    provisoire.write_bytes(contenu)
    if cible.exists():
        os.replace(cible, DONNEES / (nom + ".bak"))
    os.replace(provisoire, cible)


def etat():
    """Ce que la page de dépôt affiche : quand, et combien de personnes.

    Sans ça, on dépose sans savoir si le précédent est passé ni de quand il
    date, et on redépose « pour voir »."""
    def quand(chemin):
        if not chemin.exists():
            return None
        horodatage = datetime.fromtimestamp(chemin.stat().st_mtime, timezone.utc)
        return horodatage.strftime("%d/%m/%Y à %H:%M UTC")

    infos = {"page": quand(DONNEES / "index.html"),
             "donnees": quand(DONNEES / "synthese_elus.json"),
             "personnes": None}
    fichier = DONNEES / "synthese_elus.json"
    if fichier.exists():
        try:
            infos["personnes"] = len(
                json.loads(fichier.read_text("utf-8"))["personnes"])
        except (ValueError, KeyError, TypeError, OSError):
            infos["personnes"] = None
    return infos


@app.route("/connexion", methods=["GET", "POST"])
def connexion():
    if not MOT_DE_PASSE:
        return ("VEILLE_PASSWORD n'est pas configuré : personne ne peut entrer, "
                "et c'est volontaire.", 503)
    if request.method == "POST":
        # `compare_digest` plutôt que `==` : la comparaison ne s'arrête pas au
        # premier caractère faux, donc le temps de réponse ne dit rien.
        if secrets.compare_digest(request.form.get("mot_de_passe", ""), MOT_DE_PASSE):
            session["ok"] = True
            suite = request.args.get("suite", "")
            return redirect(suite if suite.startswith("/") else url_for("page"))
        flash("Mot de passe incorrect.", "error")
    return render_template("connexion.html")


@app.route("/deconnexion")
def deconnexion():
    session.clear()
    return redirect(url_for("connexion"))


# Un lien vers le dépôt, glissé dans la page avant </body>.
#
# La page vient d'un autre dépôt et ne connaît pas le service qui l'héberge :
# sans ça, rien n'indique où déposer les fichiers, et il faut connaître
# l'adresse par cœur. Injecter plutôt que demander une modification de la page
# évite d'avoir à la retoucher à chaque fois qu'elle est remplacée.
LIEN_DEPOT = (
    '<a href="/deposer" style="position:fixed;right:14px;bottom:14px;'
    'z-index:9999;background:#1f4e79;color:#fff;text-decoration:none;'
    'padding:8px 14px;border-radius:999px;font:600 14px system-ui,sans-serif;'
    'box-shadow:0 2px 8px rgba(0,0,0,.2)">Déposer / mettre à jour</a>'
)


def avec_lien_depot(html):
    """Insérer le lien juste avant </body>, ou à la fin si la balise manque."""
    marqueur = b"</body>"
    lien = LIEN_DEPOT.encode("utf-8")
    if marqueur in html:
        return html.replace(marqueur, lien + marqueur, 1)
    return html + lien


@app.route("/")
@connexion_requise
def page():
    """La page déposée, ou celle livrée avec l'image tant qu'il n'y en a pas.

    Sans données, la page d'Antoine affiche « Impossible de charger
    synthese_elus.json (404) », ce qui ressemble à une panne alors que c'est
    simplement un service neuf. On envoie donc vers le dépôt, où c'est écrit.
    """
    if not (DONNEES / "synthese_elus.json").exists():
        flash("Aucune donnée déposée pour l'instant : la page restera vide "
              "tant que le fichier manque. Déposez-le ici.", "error")
        return redirect(url_for("deposer"))
    source = DONNEES if (DONNEES / "index.html").exists() else PAGE_PAR_DEFAUT.parent
    fichier = source / "index.html"
    if not fichier.exists():
        return ("<h1>Veille élu·es et IA</h1><p>Aucune page déposée. "
                "Voir <a href='/deposer'>/deposer</a>.</p>", 404)
    reponse = app.response_class(
        avec_lien_depot(fichier.read_bytes()), mimetype="text/html")
    reponse.headers["X-Robots-Tag"] = "noindex, nofollow"
    reponse.headers["Cache-Control"] = "no-store"
    return reponse


@app.route("/synthese_elus.json")
@connexion_requise
def donnees():
    """Les données que la page charge. La page les demande en relatif, donc
    cette adresse doit rester à la racine."""
    if not (DONNEES / "synthese_elus.json").exists():
        abort(404)
    reponse = send_from_directory(DONNEES, "synthese_elus.json")
    reponse.headers["X-Robots-Tag"] = "noindex, nofollow"
    reponse.headers["Cache-Control"] = "no-store"
    return reponse


@app.route("/deposer", methods=["GET", "POST"])
@connexion_requise
def deposer():
    """Le dépôt depuis le navigateur. C'est le champ qui décide du nom du
    fichier écrit, pas celui du fichier choisi : on peut déposer
    « synthese_2026-10-15.json » sans rien casser."""
    if request.method == "POST":
        recus = [(nom, request.files.get(champ))
                 for champ, nom in (("donnees", "synthese_elus.json"),
                                    ("page", "index.html"))]
        recus = [(n, f) for n, f in recus if f is not None and f.filename]
        if not recus:
            flash("Aucun fichier choisi.", "error")
            return redirect(url_for("deposer"))
        for nom, fichier in recus:
            contenu = fichier.read(TAILLE_MAX + 1)
            ok, pourquoi = valide(nom, contenu)
            if not ok:
                flash(f"{nom} refusé, rien n'a été remplacé : {pourquoi}.", "error")
                continue
            ecrire(nom, contenu)
            flash(f"{nom} déposé.", "success")
        return redirect(url_for("deposer"))
    return render_template("deposer.html", etat=etat(),
                           depot=DEPOT, branche=BRANCHE)


@app.route("/recharger", methods=["POST"])
@connexion_requise
def recharger():
    """Réinstaller la page telle qu'elle est sur le dépôt.

    Même validation que le dépôt manuel : si le dépôt est injoignable ou la
    page illisible, celle en service n'est pas touchée.
    """
    try:
        contenu = lire_page_depot()
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        flash(f"Dépôt injoignable, rien n'a changé : {type(exc).__name__}: {exc}.",
              "error")
        return redirect(url_for("deposer"))
    ok, pourquoi = valide("index.html", contenu)
    if not ok:
        flash(f"Page du dépôt refusée, rien n'a changé : {pourquoi}.", "error")
        return redirect(url_for("deposer"))
    ecrire("index.html", contenu)
    flash(f"Page rechargée depuis {DEPOT} ({BRANCHE}).", "success")
    return redirect(url_for("deposer"))


@app.route("/televerser", methods=["POST"])
def televerser():
    """Le même dépôt, pour un script : le jour où la génération tourne dans un
    timer, elle poussera le JSON sans navigateur.

        curl -F fichier=@synthese_elus.json -H "X-Veille-Token: …" https://…/televerser
    """
    if not JETON:
        return ("VEILLE_UPLOAD_TOKEN n'est pas configuré.\n", 503)
    fourni = request.headers.get("X-Veille-Token") or request.form.get("token") or ""
    if not secrets.compare_digest(fourni, JETON):
        return ("Jeton invalide.\n", 403)
    fichier = request.files.get("fichier")
    if fichier is None or not fichier.filename:
        return ("Aucun fichier reçu (champ attendu : « fichier »).\n", 400)
    nom = Path(fichier.filename).name
    if nom not in FICHIERS:
        return (f"Nom refusé. Attendu : {', '.join(FICHIERS)}.\n", 400)
    contenu = fichier.read(TAILLE_MAX + 1)
    ok, pourquoi = valide(nom, contenu)
    if not ok:
        return (f"Refusé, rien n'a été remplacé : {pourquoi}.\n", 400)
    ecrire(nom, contenu)
    return (f"{nom} déposé ({len(contenu)} octets).\n", 200)


@app.route("/sante")
def sante():
    """Pour savoir si le conteneur répond sans avoir à se connecter."""
    return {"ok": True, **etat()}


if __name__ == "__main__":
    app.run(debug=True, port=8000)
