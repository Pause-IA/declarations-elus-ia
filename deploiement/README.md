# Mise en service sur le serveur

Ces fichiers ne font rien tant que personne ne les installe : ce sont des
unités systemd posées dans le dépôt, à copier sur la machine. Le détail des
chemins ci-dessous est celui du serveur de Pause IA.

## Avant de commencer

Le dépôt et les données sont séparés : le code est remplacé à chaque `git
pull`, les données et l'état (`deja_vus.json`, les caches) doivent lui
survivre.

```bash
# Un utilisateur sans privilèges : ce travail télécharge et analyse des
# fichiers venus d'Internet, il n'a aucune raison de tourner en root.
sudo useradd --system --create-home --shell /usr/sbin/nologin veille

sudo apt-get install -y curl unzip zstd python3

sudo git clone https://github.com/Pause-IA/declarations-elus-ia \
  /opt/declarations-elus-ia
sudo mkdir -p /opt/volunteer-apps/data/veille-sources
sudo chown -R veille:veille /opt/volunteer-apps/data/veille-sources
```

## Le jeton de dépôt, et lui seul

Le travail publie son résultat par HTTP sur `/televerser`. Il a besoin du
jeton, pas du mot de passe du site ni de la clé de session — qui vivent dans
`veille-elus.env` et n'ont rien à faire dans l'environnement d'un script qui
tourne chaque nuit.

```bash
sudo grep '^VEILLE_UPLOAD_TOKEN=' /opt/volunteer-apps/secrets/veille-elus.env \
  | sudo tee /opt/volunteer-apps/secrets/veille-maj.env > /dev/null
sudo chmod 600 /opt/volunteer-apps/secrets/veille-maj.env
sudo chown root:veille /opt/volunteer-apps/secrets/veille-maj.env
sudo chmod 640 /opt/volunteer-apps/secrets/veille-maj.env
```

## Un premier passage à la main, avant d'activer le timer

Le serveur a 4 Go de mémoire et héberge déjà plusieurs applications. Ce script
décompresse le dump des débats de l'Assemblée **et** celui de Parltrack, puis
les analyse. `Nice=10` protège du ralentissement, pas d'un manque de mémoire.
Donc on regarde une fois, en direct, avant d'automatiser :

```bash
sudo -u veille env $(sudo cat /opt/volunteer-apps/secrets/veille-maj.env | xargs) \
  /opt/declarations-elus-ia/scripts/mise_a_jour.sh \
  /opt/volunteer-apps/data/veille-sources
```

Dans une autre session pendant ce temps : `free -m` et `df -h /`. Si le
processus est tué (`Killed`, code 137), c'est la mémoire, et il faudra découper
l'analyse avant d'automatiser.

## Installer le timer

```bash
sudo cp /opt/declarations-elus-ia/deploiement/veille-maj.{service,timer} \
  /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now veille-maj.timer
systemctl list-timers veille-maj.timer
```

`OnFailure=alerte@%n.service` suppose que l'unité modèle d'alerte est installée
sur la machine : c'est celle qu'utilisent déjà les travaux du CRM
(`sync-officials`, `backup-db`, les imports de courriels). Vérifier :

```bash
systemctl cat alerte@.service > /dev/null && echo "alerte disponible"
```

Si elle manque, retirer la ligne `OnFailure=` — mais alors une mise à jour qui
échoue ne se signalera nulle part.

## Mettre à jour le code ensuite

```bash
sudo git -C /opt/declarations-elus-ia pull
# si les unités ont changé :
sudo cp /opt/declarations-elus-ia/deploiement/veille-maj.{service,timer} \
  /etc/systemd/system/ && sudo systemctl daemon-reload
```

## Vérifier que ça tourne

```bash
systemctl list-timers veille-maj.timer          # prochain passage
journalctl -u veille-maj.service -n 40 --no-pager
curl -s https://veille.pauseia.fr/sante         # date du dernier dépôt
```

`/sante` répond sans connexion et donne la date du dernier fichier déposé :
c'est le moyen le plus court de savoir si la chaîne complète fonctionne.
