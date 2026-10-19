#!/usr/bin/env bash
# Mise à jour complète de la veille : téléchargements, scripts, synthèse, publication.
#
# Usage : scripts/mise_a_jour.sh [dossier_des_données]
# Publication sur le site seulement si VEILLE_UPLOAD_TOKEN est défini
# (adresse réglable par VEILLE_URL, https://veille.pauseia.fr par défaut).
set -euo pipefail

SCRIPTS="$(cd "$(dirname "$0")/exploration" && pwd)"
DONNEES="${1:-$HOME/PauseIA/donnees-veille}"
mkdir -p "$DONNEES"
cd "$DONNEES"

# Un seul lancement à la fois : si le précédent tourne encore, on n'en démarre pas un second
exec 9>.verrou
flock -n 9 || { echo "Une mise à jour est déjà en cours, abandon."; exit 0; }

etape() { echo; echo "== $(date '+%H:%M:%S') $*"; }

# Une source qui échoue ne doit pas coûter les autres. Le script d'exploration
# qui tombe laisse son CSV du passage précédent en place, la synthèse travaille
# avec, la page est publiée — et on sort quand même en erreur à la fin pour que
# l'alerte parte. Sans ce dernier point, une source en panne depuis des semaines
# ne se verrait pas : la page resterait fraîche avec des données figées.
ECHECS=()
explorer() {
    local script="$1"
    if ! python3 "$SCRIPTS/$script" > /dev/null; then
        echo "  ✗ $script a échoué — on garde ses données du passage précédent" >&2
        ECHECS+=("$script")
    fi
}

# Télécharge seulement si la source a changé depuis notre copie.
# Renvoie 0 si le fichier a été mis à jour, 1 s'il est inchangé ; arrête tout en cas d'erreur.
telecharger() {
    local fichier="$1" adresse="$2" code
    local options=(-sSL -R --retry 3 -o "$fichier.tmp" -w '%{http_code}')
    [ -f "$fichier" ] && options+=(-z "$fichier")
    code=$(curl "${options[@]}" "$adresse") || code="erreur"
    if [ "$code" = 200 ]; then
        mv "$fichier.tmp" "$fichier"
        echo "  ↓ $fichier mis à jour"
        return 0
    fi
    rm -f "$fichier.tmp"
    if [ "$code" = 304 ]; then
        echo "  = $fichier inchangé"
        return 1
    fi
    echo "  ✗ $fichier : échec ($code)" >&2
    exit 1
}

etape "Téléchargements"
if telecharger an-debats.zip \
    https://data.assemblee-nationale.fr/static/openData/repository/17/vp/syceronbrut/syseron.xml.zip \
    || [ ! -d an ]; then
    rm -rf an && unzip -q an-debats.zip -d an
fi
telecharger senat-cri.zip https://data.senat.fr/data/debats/cri.zip || true
telecharger an-questions.zip \
    https://data.assemblee-nationale.fr/static/openData/repository/17/questions/questions_ecrites/Questions_ecrites.json.zip || true
telecharger senat-questions.csv https://data.senat.fr/data/questions/questions-depuis-un-an.csv || true
if telecharger parltrack-activities.json.zst https://parltrack.org/dumps/ep_mep_activities.json.zst \
    || [ ! -f parltrack-activities.json ]; then
    zstd -d -f -q -o parltrack-activities.json parltrack-activities.json.zst
fi
telecharger deputes_datan.csv \
    "https://www.data.gouv.fr/api/1/datasets/r/092bd7bb-1543-405b-b53c-932ebb49bb8e" || true
telecharger senateurs.csv https://data.senat.fr/data/senateurs/ODSEN_GENERAL.csv || true

etape "Séances"
explorer explore_an.py
explorer explore_senat.py
explorer explore_pe.py

etape "Questions écrites"
explorer explore_an_questions.py
explorer explore_senat_questions.py
explorer textes_senat_questions.py
explorer explore_pe_questions.py
explorer explore_pe_questions_api.py

etape "Synthèse"
python3 "$SCRIPTS/synthese.py" > synthese.log
grep -E "Mémoire|🔔|personnes au total" synthese.log || true

etape "Publication"
if [ -n "${VEILLE_UPLOAD_TOKEN:-}" ]; then
    curl -fsS -F fichier=@synthese_elus.json \
         -H "X-Veille-Token: $VEILLE_UPLOAD_TOKEN" \
         "${VEILLE_URL:-https://veille.pauseia.fr}/televerser" > /dev/null
    echo "  ✓ synthese_elus.json publié"
else
    echo "  (VEILLE_UPLOAD_TOKEN absent : rien n'est publié, le fichier est prêt dans $DONNEES)"
fi
if [ ${#ECHECS[@]} -gt 0 ]; then
    etape "Terminé, avec des sources en échec"
    printf '  ✗ %s\n' "${ECHECS[@]}" >&2
    echo "La page est à jour pour les autres sources ; celles-ci gardent leurs" >&2
    echo "données du passage précédent." >&2
    exit 1
fi

etape "Terminé"