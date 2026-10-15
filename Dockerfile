FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir flask gunicorn

# La page livrée avec l'image sert tant que personne n'en a déposé une autre :
# un déploiement neuf affiche déjà quelque chose.
COPY page/ ./page/
COPY serveur/ ./serveur/

# Les fichiers déposés vivent ici, dans un volume : ils survivent aux
# reconstructions, contrairement à tout ce qui précède.
RUN mkdir -p /data
ENV VEILLE_DATA_DIR=/data

EXPOSE 8000

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8000", \
     "--access-logfile", "-", "--error-logfile", "-", \
     "--chdir", "/app/serveur", "app:app"]
