"""La fonction de téléchargement de mise_a_jour.sh, face à une source en panne.

Le 20/10/2026 le serveur de l'Assemblée a coupé une connexion en cours
(« curl: (92) HTTP/2 stream 1 was not closed cleanly: PROTOCOL_ERROR »), et le
passage s'est arrêté net sur la première source : les cinq autres n'ont même pas
été tentées. La tolérance posée la veille ne couvrait que l'analyse, pas les
téléchargements.

Le test extrait la vraie fonction du script et la fait tourner avec un faux
curl : ce qui est vérifié est le code qui part en production, pas une copie.
"""
import os
import re
import subprocess
import tempfile
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(RACINE, "scripts", "mise_a_jour.sh")


def fonction_telecharger():
    """Le texte de telecharger(), extrait du script tel qu'il est livré."""
    with open(SCRIPT, encoding="utf-8") as f:
        source = f.read()
    debut = source.index("telecharger() {")
    fin = source.index("\n}\n", debut) + len("\n}\n")
    return source[debut:fin]


class TestTelecharger(unittest.TestCase):
    def lancer(self, code_curl, sortie_curl="", fichier_existe=False):
        """Joue telecharger() avec un curl truqué. Rend (code de retour, texte)."""
        with tempfile.TemporaryDirectory() as dossier:
            faux_curl = os.path.join(dossier, "curl")
            with open(faux_curl, "w", encoding="utf-8") as f:
                f.write(f'#!/bin/sh\nprintf "%s" "{sortie_curl}"\nexit {code_curl}\n')
            os.chmod(faux_curl, 0o755)
            if fichier_existe:
                with open(os.path.join(dossier, "source.zip"), "w") as f:
                    f.write("copie precedente")
            programme = (
                "set -euo pipefail\n"
                "ECHECS=()\n"
                + fonction_telecharger()
                + '\nif telecharger source.zip https://exemple/source.zip; then\n'
                '    echo "RETOUR=0"\n'
                'else\n'
                '    echo "RETOUR=1"\n'
                'fi\n'
                'printf "ECHECS=%s\\n" "${#ECHECS[@]}"\n'
            )
            r = subprocess.run(["bash", "-c", programme], cwd=dossier,
                               capture_output=True, text=True,
                               env={**os.environ, "PATH": dossier + ":" + os.environ["PATH"]})
            return r.returncode, r.stdout + r.stderr

    def test_mise_a_jour(self):
        code, texte = self.lancer(0, "200")
        self.assertEqual(code, 0)
        self.assertIn("mis à jour", texte)
        self.assertIn("RETOUR=0", texte)
        self.assertIn("ECHECS=0", texte)

    def test_inchange(self):
        code, texte = self.lancer(0, "304", fichier_existe=True)
        self.assertEqual(code, 0)
        self.assertIn("inchangé", texte)
        self.assertIn("ECHECS=0", texte)

    def test_coupure_avec_copie_precedente(self):
        """Le cas réel : curl échoue, mais on a la copie d'hier."""
        code, texte = self.lancer(92, "", fichier_existe=True)
        self.assertEqual(code, 0, "le script ne doit pas s'arrêter")
        self.assertIn("on garde la copie précédente", texte)
        self.assertIn("RETOUR=1", texte)
        self.assertIn("ECHECS=1", texte, "l'échec doit être retenu pour l'alerte")

    def test_erreur_http_avec_copie_precedente(self):
        code, texte = self.lancer(0, "503", fichier_existe=True)
        self.assertEqual(code, 0)
        self.assertIn("ECHECS=1", texte)

    def test_coupure_sans_copie_precedente(self):
        """Rien en réserve : là il faut bien s'arrêter, il n'y a rien à analyser."""
        code, texte = self.lancer(92, "")
        self.assertNotEqual(code, 0)
        self.assertIn("aucune copie précédente", texte)

    def test_le_fichier_precedent_nest_pas_ecrase(self):
        """Un .tmp partiel ne doit jamais remplacer une copie qui marche."""
        with tempfile.TemporaryDirectory() as dossier:
            faux_curl = os.path.join(dossier, "curl")
            with open(faux_curl, "w", encoding="utf-8") as f:
                # écrit un .tmp tronqué, puis échoue
                f.write('#!/bin/sh\necho tronque > source.zip.tmp\nexit 92\n')
            os.chmod(faux_curl, 0o755)
            cible = os.path.join(dossier, "source.zip")
            with open(cible, "w") as f:
                f.write("copie complete")
            programme = ("set -euo pipefail\nECHECS=()\n" + fonction_telecharger()
                         + "\ntelecharger source.zip https://exemple/source.zip || true\n")
            subprocess.run(["bash", "-c", programme], cwd=dossier,
                           capture_output=True, text=True,
                           env={**os.environ, "PATH": dossier + ":" + os.environ["PATH"]})
            with open(cible) as f:
                self.assertEqual(f.read(), "copie complete")
            self.assertFalse(os.path.exists(cible + ".tmp"), "le .tmp doit être nettoyé")


class TestOptionsCurl(unittest.TestCase):
    def test_http11_et_reprises(self):
        """HTTP/2 est ce qui a cassé, et --retry seul ignore ce type de coupure."""
        texte = fonction_telecharger()
        self.assertIn("--http1.1", texte)
        self.assertIn("--retry-all-errors", texte)


if __name__ == "__main__":
    unittest.main()
