"""Les identifiants officiels dans synthese_elus.json.

Le CRM affiche sur la fiche de chaque élu·e ses passages sur l'IA trouvés par
la veille (demande de Romain, 27/10/2026). Pour relier un·e élu·e à sa fiche
sans se fier au seul nom (homonymes, accents, noms composés), la synthèse
recopie l'identifiant officiel qu'elle lit déjà dans les sources : PA… pour
l'Assemblée, matricule pour le Sénat, numéro pour le Parlement européen.
"""
import csv
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "scripts", "exploration"))

import synthese  # noqa: E402

TEXTE = "Je m'inquiète des risques de l'intelligence artificielle pour l'emploi."


def ecrire(chemin, lignes):
    champs = sorted({c for ligne in lignes for c in ligne})
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=champs)
        w.writeheader()
        w.writerows(lignes)


class IdentifiantsOfficiels(unittest.TestCase):
    def setUp(self):
        self.ancien = os.getcwd()
        self.dossier = tempfile.mkdtemp()
        os.chdir(self.dossier)
        self.addCleanup(os.chdir, self.ancien)

    def synthese(self):
        with redirect_stdout(StringIO()):
            synthese.main()
        with open("synthese_elus.json", encoding="utf-8") as f:
            return {p["nom"]: p for p in json.load(f)["personnes"]}

    def test_les_trois_chambres(self):
        ecrire("passages_an.csv", [{
            "date": "2026-10-01", "orateur": "Alain David", "id_acteur": "PA1008",
            "texte": TEXTE, "url": "https://www.assemblee-nationale.fr/x"}])
        ecrire("passages_senat.csv", [{
            "date": "2026-10-02", "orateur": "Bruno Sido", "matricule": "01058X",
            "texte": TEXTE, "url": "https://www.senat.fr/x"}])
        ecrire("passages_pe.csv", [{
            "date": "2026-10-03", "orateur": "Grégory Allione", "id_pe": "256869",
            "texte": TEXTE, "id": "x"}])
        personnes = self.synthese()
        self.assertEqual(personnes["Alain David"]["ids_officiels"], ["PA1008"])
        self.assertEqual(personnes["Bruno Sido"]["ids_officiels"], ["01058X"])
        self.assertEqual(personnes["Grégory Allione"]["ids_officiels"], ["256869"])

    def test_sans_identifiant_liste_vide(self):
        # Une ligne sans identifiant (source ancienne) : la clé existe, vide.
        ecrire("passages_an.csv", [{
            "date": "2026-10-01", "orateur": "Jeanne Martin", "texte": TEXTE}])
        self.assertEqual(self.synthese()["Jeanne Martin"]["ids_officiels"], [])


if __name__ == "__main__":
    unittest.main()
