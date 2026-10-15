"""Le service qui sert la page et accepte son dépôt.

Ce qui est verrouillé ici : rien n'est servi sans mot de passe, un fichier
abîmé ne remplace jamais celui qui marche, et le dépôt se fait depuis un
navigateur — sans quoi chaque mise à jour passerait par une personne ayant les
accès au serveur, qui deviendrait le goulot d'étranglement.
"""
import importlib
import io
import json
import os
import sys
import tempfile
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "serveur"))

JSON_VALIDE = json.dumps({
    "genere_le": "2026-10-15",
    "personnes": [{"nom": "Aurélien Saintoul", "chambre": "Assemblée nationale"}],
}).encode("utf-8")


class ServeurTests(unittest.TestCase):
    def setUp(self):
        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        os.environ["VEILLE_DATA_DIR"] = dossier.name
        os.environ["VEILLE_PASSWORD"] = "secret"
        os.environ["VEILLE_UPLOAD_TOKEN"] = "jeton"
        os.environ["VEILLE_SECRET_KEY"] = "pour-les-tests"
        import app as module                          # noqa: PLC0415
        self.module = importlib.reload(module)
        self.module.app.config["TESTING"] = True
        self.client = self.module.app.test_client()
        self.dossier = self.module.DONNEES

    def connecte(self):
        self.client.post("/connexion", data={"mot_de_passe": "secret"})

    def depose_formulaire(self, champ, nom, contenu):
        return self.client.post(
            "/deposer", data={champ: (io.BytesIO(contenu), nom)},
            content_type="multipart/form-data", follow_redirects=True)

    # --- l'accès ----------------------------------------------------------
    def test_la_page_nest_pas_servie_sans_mot_de_passe(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/connexion", r.headers["Location"])

    def test_les_donnees_non_plus(self):
        self.assertEqual(self.client.get("/synthese_elus.json").status_code, 302)

    def test_le_formulaire_non_plus(self):
        self.assertEqual(self.client.get("/deposer").status_code, 302)

    def test_un_mauvais_mot_de_passe_ne_connecte_pas(self):
        self.client.post("/connexion", data={"mot_de_passe": "presque"})
        self.assertEqual(self.client.get("/deposer").status_code, 302)

    def test_le_bon_mot_de_passe_connecte(self):
        self.connecte()
        self.assertEqual(self.client.get("/deposer").status_code, 200)

    def test_sans_mot_de_passe_configure_personne_nentre(self):
        self.module.MOT_DE_PASSE = ""
        r = self.client.get("/connexion")
        self.assertEqual(r.status_code, 503)

    def test_la_redirection_apres_connexion_reste_sur_le_site(self):
        # Sans ce garde-fou, « ?suite=https://ailleurs » ferait du service un
        # tremplin vers n'importe quel site.
        r = self.client.post("/connexion?suite=https://exemple.test/piege",
                             data={"mot_de_passe": "secret"})
        self.assertNotIn("exemple.test", r.headers["Location"])

    # --- la page par défaut ----------------------------------------------
    def test_sans_page_deposee_celle_du_depot_est_servie(self):
        self.connecte()
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Veille", r.data)

    def test_une_page_deposee_remplace_celle_du_depot(self):
        self.connecte()
        self.depose_formulaire("page", "index.html", b"<html>ma version</html>")
        self.assertIn(b"ma version", self.client.get("/").data)

    # --- le dépôt ---------------------------------------------------------
    def test_deposer_les_donnees_les_rend_lisibles(self):
        self.connecte()
        self.depose_formulaire("donnees", "synthese_elus.json", JSON_VALIDE)
        self.assertEqual(self.client.get("/synthese_elus.json").data, JSON_VALIDE)

    def test_le_champ_decide_du_nom_pas_le_fichier_choisi(self):
        self.connecte()
        self.depose_formulaire("donnees", "export_du_15.json", JSON_VALIDE)
        self.assertEqual((self.dossier / "synthese_elus.json").read_bytes(),
                         JSON_VALIDE)

    def test_un_json_tronque_ne_remplace_pas_le_bon(self):
        self.connecte()
        self.depose_formulaire("donnees", "synthese_elus.json", JSON_VALIDE)
        r = self.depose_formulaire("donnees", "x.json", b'{"personnes": [')
        self.assertIn("refusé", r.data.decode())
        self.assertEqual((self.dossier / "synthese_elus.json").read_bytes(),
                         JSON_VALIDE)

    def test_un_json_sans_personne_est_refuse(self):
        self.connecte()
        vide = json.dumps({"genere_le": "2026-10-15", "personnes": []}).encode()
        r = self.depose_formulaire("donnees", "x.json", vide)
        self.assertIn("refusé", r.data.decode())

    def test_sans_fichier_choisi_on_le_dit(self):
        self.connecte()
        r = self.client.post("/deposer", data={},
                             content_type="multipart/form-data",
                             follow_redirects=True)
        self.assertIn("Aucun fichier choisi", r.data.decode())

    def test_la_version_precedente_est_gardee(self):
        self.connecte()
        self.depose_formulaire("donnees", "synthese_elus.json", JSON_VALIDE)
        autre = json.dumps({"genere_le": "2026-10-16",
                            "personnes": [{"nom": "X"}]}).encode()
        self.depose_formulaire("donnees", "synthese_elus.json", autre)
        self.assertEqual((self.dossier / "synthese_elus.json.bak").read_bytes(),
                         JSON_VALIDE)

    def test_aucun_fichier_provisoire_ne_reste(self):
        self.connecte()
        self.depose_formulaire("donnees", "synthese_elus.json", JSON_VALIDE)
        self.assertEqual(list(self.dossier.glob("*.tmp")), [])

    def test_letat_dit_la_date_et_le_nombre(self):
        self.connecte()
        self.depose_formulaire("donnees", "synthese_elus.json", JSON_VALIDE)
        self.assertIn("1 personne(s)", self.client.get("/deposer").data.decode())

    # --- le dépôt par jeton, pour un script -------------------------------
    def test_le_jeton_permet_de_deposer_sans_session(self):
        r = self.client.post(
            "/televerser",
            data={"fichier": (io.BytesIO(JSON_VALIDE), "synthese_elus.json")},
            headers={"X-Veille-Token": "jeton"},
            content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200)
        self.assertTrue((self.dossier / "synthese_elus.json").exists())

    def test_un_mauvais_jeton_nécrit_rien(self):
        r = self.client.post(
            "/televerser",
            data={"fichier": (io.BytesIO(JSON_VALIDE), "synthese_elus.json")},
            headers={"X-Veille-Token": "presque"},
            content_type="multipart/form-data")
        self.assertEqual(r.status_code, 403)
        self.assertFalse((self.dossier / "synthese_elus.json").exists())

    def test_un_nom_de_fichier_hors_liste_est_refuse(self):
        r = self.client.post(
            "/televerser",
            data={"fichier": (io.BytesIO(b"x"), "../app.py")},
            headers={"X-Veille-Token": "jeton"},
            content_type="multipart/form-data")
        self.assertEqual(r.status_code, 400)

    def test_la_sante_repond_sans_connexion(self):
        r = self.client.get("/sante")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["ok"])


if __name__ == "__main__":
    unittest.main()
