# declarations-elus-ia
Repérage des prises de parole des parlementaires français sur les risques majeurs de l’IA. Sources officielles en open data : Assemblée nationale, Sénat, Parlement européen.

## État actuel

- Veille en ligne sur https://veille.pauseia.fr/ (accès réservé à l'équipe) :
  528 personnes, alertes sur les nouveaux propos importants.
- Mise à jour quotidienne automatique prête (`scripts/mise_a_jour.sh` et
  `deploiement/`), en attente d'activation sur le serveur.
- Étude de faisabilité, sources, mots-clés et limites :
  [docs/etude-faisabilite.md](docs/etude-faisabilite.md).

## Mettre à jour la veille

Python 3 (bibliothèque standard uniquement), `curl`, `unzip`, `zstd` et `flock`.
Toute la chaîne tient en une commande :

```bash
scripts/mise_a_jour.sh [dossier_des_données]   # par défaut ~/PauseIA/donnees-veille
```

Le script :

1. **télécharge les sources seulement si elles ont changé** (`curl -z`) : un
   lancement sans nouveauté ne retélécharge rien, pas même les 545 Mo du Sénat ;
2. lance les scripts d'exploration (séances, puis questions écrites) ;
3. lance la synthèse, qui écrit `synthese_elus.json` et met à jour la mémoire
   des alertes (`deja_vus.json`) ;
4. **publie** `synthese_elus.json` sur le site via `/televerser`, seulement si
   `VEILLE_UPLOAD_TOKEN` est défini (adresse réglable par `VEILLE_URL`).

Il s'arrête à la première erreur (`set -euo pipefail`) et refuse de se lancer
deux fois en même temps (`flock`). Si la synthèse ne trouve aucune donnée, elle
s'arrête sans rien écrire : rien n'est publié, le site garde sa version
précédente. Compter environ 6 minutes la première fois, 4 ensuite.

### Lancement quotidien

`deploiement/veille-maj.service` et `deploiement/veille-maj.timer` lancent la
mise à jour chaque jour à 6 h (heure de Paris), avec rattrapage si le serveur
était éteint (`Persistent=true`). Chemins et utilisateur à adapter, puis :

    sudo cp deploiement/veille-maj.* /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable --now veille-maj.timer

Vérifier : `systemctl list-timers veille-maj.timer` (prochain lancement) et
`journalctl -u veille-maj.service` (journal du dernier lancement).

**À conserver** dans le dossier des données d'un lancement à l'autre :
`deja_vus.json` (sans elle, le lancement suivant repart « à blanc », sans
alerte) et `pe_questions_fiches.json` (cache du PE, sinon environ 30 min pour
tout relire).

### Les scripts un par un

Depuis le dossier des données, `python3 <chemin>/scripts/exploration/<script>.py` :

| Script | Source |
|---|---|
| `explore_an.py`, `explore_an_questions.py` | open data de l'Assemblée nationale (séances, questions écrites) |
| `explore_senat.py`, `explore_senat_questions.py`, `textes_senat_questions.py` | open data du Sénat ; textes des questions sur senat.fr |
| `explore_pe.py` | API du Parlement européen (séances) |
| `explore_pe_questions.py` | Parltrack : questions écrites du PE jusqu'au 15/07/2026 |
| `explore_pe_questions_api.py` | API du Parlement européen : questions écrites depuis le 16/07/2026 |
| `synthese.py` | fusionne tout : `synthese_elus.csv` (Excel), `synthese_elus.json` (site) |

Chaque script affiche un résumé et écrit le détail en CSV. Les données
téléchargées et les résultats sont ignorés par Git.

## La page de veille, en ligne

La page est servie par une petite application Flask (`serveur/`), déployée dans
son propre conteneur à côté du CRM. Elle fait deux choses : servir la page
derrière un mot de passe, et accepter son dépôt depuis le navigateur.

Pourquoi un service séparé du CRM plutôt qu'une route dedans : la veille évolue
vite et appartient à ce projet, donc chaque changement n'a pas à passer par une
relecture sur le dépôt du CRM. Et son JavaScript ne tourne pas sur l'origine du
CRM, donc il ne peut rien lire des fiches ni des courriels.

### Déposer les fichiers

Depuis le navigateur, sur `/deposer`, après connexion : un champ pour
`synthese_elus.json`, un autre pour `index.html` quand la présentation change.
Le champ décide du nom écrit, pas celui du fichier choisi — déposer
`synthese_2026-10-15.json` fonctionne.

Un fichier illisible est refusé **avant** de remplacer celui qui marche, le
remplacement est atomique, et la version précédente reste en `.bak`.

### Mettre la page à jour depuis le dépôt

Il y a deux copies d'`index.html` : celle du dépôt (`page/index.html`) et celle
déposée. **C'est la déposée qui s'affiche** — modifier la page dans le dépôt et
pousser ne change donc rien en ligne.

Le bouton « Recharger depuis le dépôt », sur `/deposer`, réinstalle
`page/index.html` tel qu'il est sur la branche `main`. Le dépôt redevient la
seule référence : on pousse, on clique, c'est en ligne. Si le dépôt est
injoignable ou la page illisible, celle en service n'est pas touchée.

Réglable par `VEILLE_DEPOT` et `VEILLE_BRANCHE`, et `VEILLE_GITHUB_TOKEN` si le
dépôt passe en privé. L'adresse est construite à partir de cette configuration
et jamais de la requête : un champ « URL à charger » ferait de ce service un
moyen de frapper n'importe quelle machine depuis l'intérieur du réseau.

C'est ce que fait `scripts/mise_a_jour.sh` (voir « Mettre à jour la veille ») :

    curl -F fichier=@synthese_elus.json \
         -H "X-Veille-Token: $VEILLE_UPLOAD_TOKEN" https://…/televerser

### Déployer

Le fichier de secrets, `/opt/volunteer-apps/secrets/veille-elus.env` :

    VEILLE_PASSWORD=…            # ce que l'équipe plaidoyer saisit
    VEILLE_SECRET_KEY=…          # openssl rand -hex 32, sinon les sessions
                                 # tombent à chaque redémarrage
    VEILLE_UPLOAD_TOKEN=…        # facultatif, seulement pour le dépôt par script

Puis, sur le serveur :

    sudo docker compose up -d --build

Le proxy inverse est **Caddy**, pas Traefik. Il faut lui déclarer le domaine,
dans `/opt/volunteer-apps/caddy/Caddyfile`, sur le modèle des autres sites :

    veille.pauseia.fr {
        reverse_proxy veille-elus-ia:8000
    }

puis recharger sans couper les autres sites :

    sudo docker exec caddy caddy reload --config /etc/caddy/Caddyfile

Sans cette entrée, le conteneur tourne, répond sur le réseau interne, et le
domaine échoue en « tlsv1 alert internal error » : Caddy reçoit une demande
pour un nom qu'il ne connaît pas et ne peut présenter aucun certificat. Le
symptôme ne ressemble pas à sa cause, d'où cette note.

Les fichiers déposés vivent dans `/opt/volunteer-apps/data/veille-elus`, hors
de l'image : ils survivent aux reconstructions. La page livrée avec l'image
sert tant que personne n'en a déposé une autre, donc un déploiement neuf
affiche déjà quelque chose et il ne reste qu'à déposer le JSON.

`/sante` répond sans connexion et dit si un fichier est déposé, pour vérifier
que le conteneur répond.
