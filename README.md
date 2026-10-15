# declarations-elus-ia
Repérage des prises de parole des parlementaires français sur les risques majeurs de l’IA. Sources officielles en open data : Assemblée nationale, Sénat, Parlement européen.

## État actuel

Étude de faisabilité terminée : voir [docs/etude-faisabilite.md](docs/etude-faisabilite.md).

## Lancer les scripts d'exploration

Python 3, bibliothèque standard uniquement. Les données sont téléchargées dans un
dossier `donnees/`, ignoré par Git, et les scripts se lancent depuis ce dossier.

```bash
mkdir -p donnees && cd donnees

# Assemblée nationale
curl -L -o an-debats.zip https://data.assemblee-nationale.fr/static/openData/repository/17/vp/syceronbrut/syseron.xml.zip
unzip -q an-debats.zip -d an
python3 ../scripts/exploration/explore_an.py

# Sénat (lu directement dans le ZIP, sans décompresser)
curl -L -o senat-cri.zip https://data.senat.fr/data/debats/cri.zip
python3 ../scripts/exploration/explore_senat.py

# Parlement européen (API, rien à télécharger)
python3 ../scripts/exploration/explore_pe.py
```

`explore_pe.py` récupère la liste des eurodéputé·es français·es en poste
directement depuis l'API du Parlement européen : rien d'autre à installer.

Chaque script affiche un résumé et écrit le détail en CSV.

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

Pour un script, le jour où la génération tournera dans un timer :

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

Les fichiers déposés vivent dans `/opt/volunteer-apps/data/veille-elus`, hors
de l'image : ils survivent aux reconstructions. La page livrée avec l'image
sert tant que personne n'en a déposé une autre, donc un déploiement neuf
affiche déjà quelque chose et il ne reste qu'à déposer le JSON.

`/sante` répond sans connexion et dit si un fichier est déposé, pour vérifier
que le conteneur répond.
