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
