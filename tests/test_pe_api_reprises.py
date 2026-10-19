"""Les reprises face à une source intermittente, et la fin de liste.

Le 19/10/2026 l'API du Parlement européen a renvoyé « HTTP 500 » environ une
fois sur cinq, de façon intermittente : la même adresse demandée cinq fois a
répondu quatre fois 200 et une fois 500. Trois scripts l'interrogeaient sans
aucune reprise, et le premier échec faisait tomber tout le passage quotidien —
alors que les cinq autres sources étaient en bon état. Ces cas figent la règle.
"""
import io
import os
import sys
import unittest
import urllib.error

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "scripts", "exploration"))

import explore_pe_questions_api as pe  # noqa: E402
import reseau  # noqa: E402


class Reponse(io.BytesIO):
    """Ce que urlopen rend, en gestionnaire de contexte."""

    def __init__(self, corps=b"{}", status=200):
        super().__init__(corps)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def erreur(code):
    return urllib.error.HTTPError("http://x", code, "", None, None)


class FauxReseau:
    """Rejoue une suite de réponses ou d'erreurs, et compte les appels."""

    def __init__(self, *suite):
        self.suite = list(suite)
        self.appels = 0

    def __call__(self, requete, timeout=None):
        self.appels += 1
        prochaine = self.suite.pop(0) if self.suite else Reponse()
        if isinstance(prochaine, Exception):
            raise prochaine
        return prochaine


class SansReseau(unittest.TestCase):
    """Remplace le réseau et l'attente, et tait les avertissements."""

    def setUp(self):
        self.vrai_urlopen = reseau.urllib.request.urlopen
        self.vrai_sleep = reseau.time.sleep
        reseau.time.sleep = lambda _: None
        pe.INCOMPLET.clear()
        self.vrai_stderr, sys.stderr = sys.stderr, io.StringIO()

    def tearDown(self):
        reseau.urllib.request.urlopen = self.vrai_urlopen
        reseau.time.sleep = self.vrai_sleep
        sys.stderr = self.vrai_stderr
        pe.INCOMPLET.clear()

    def repond(self, *suite):
        faux = FauxReseau(*suite)
        reseau.urllib.request.urlopen = faux
        return faux


class TestLireJson(SansReseau):
    def test_500_passager_puis_succes(self):
        """Le cas réel : un 500 isolé ne doit plus rien casser."""
        faux = self.repond(erreur(500), Reponse(b'{"data": []}'))
        self.assertEqual(reseau.lire_json("http://x"), {"data": []})
        self.assertEqual(faux.appels, 2)

    def test_plusieurs_500_de_suite(self):
        faux = self.repond(erreur(500), erreur(503), erreur(500),
                           Reponse(b'{"data": [1]}'))
        self.assertEqual(reseau.lire_json("http://x"), {"data": [1]})
        self.assertEqual(faux.appels, 4)

    def test_429_est_reessaye(self):
        self.repond(erreur(429), Reponse(b"{}"))
        self.assertEqual(reseau.lire_json("http://x"), {})

    def test_panne_reseau_est_reessayee(self):
        self.repond(urllib.error.URLError("coupure"), Reponse(b"{}"))
        self.assertEqual(reseau.lire_json("http://x"), {})

    def test_abandon_apres_toutes_les_tentatives(self):
        faux = self.repond(*[erreur(500)] * reseau.ESSAIS)
        with self.assertRaises(urllib.error.HTTPError):
            reseau.lire_json("http://x")
        self.assertEqual(faux.appels, reseau.ESSAIS)

    def test_404_nest_pas_reessaye(self):
        """Une erreur de notre requête : la réessayer ne sert à rien."""
        faux = self.repond(erreur(404), Reponse(b"{}"))
        with self.assertRaises(urllib.error.HTTPError):
            reseau.lire_json("http://x")
        self.assertEqual(faux.appels, 1)

    def test_204_est_une_fin_de_liste(self):
        """204 No Content : pas une erreur, le corps est simplement vide."""
        self.repond(Reponse(b"", status=204))
        self.assertEqual(reseau.lire_json("http://x"), {})

    def test_corps_vide_en_200(self):
        self.repond(Reponse(b"   "))
        self.assertEqual(reseau.lire_json("http://x"), {})

    def test_lire_texte(self):
        self.repond(erreur(500), Reponse("Assemblée".encode("utf-8")))
        self.assertEqual(reseau.lire_texte("http://x"), "Assemblée")


class TestIdentifiants(SansReseau):
    """La pagination des questions, qui est ce qui a cassé en production."""

    def page(self, combien, depart=0):
        corps = b'{"data": [' + b", ".join(
            b'{"identifier": "Q-%d"}' % (depart + i) for i in range(combien)) + b"]}"
        return Reponse(corps)

    def test_une_page_incomplete_arrete_la_pagination(self):
        self.repond(self.page(3))
        self.assertEqual(pe.identifiants(2026, "QUESTION_WRITTEN"),
                         ["Q-0", "Q-1", "Q-2"])
        self.assertEqual(pe.INCOMPLET, [])

    def test_page_en_echec_rend_une_liste_partielle(self):
        """Mieux vaut les 100 premiers identifiants que rien du tout."""
        self.repond(self.page(pe.PAR_PAGE),
                    *[erreur(500)] * reseau.ESSAIS)
        obtenus = pe.identifiants(2026, "QUESTION_WRITTEN")
        self.assertEqual(len(obtenus), pe.PAR_PAGE)
        self.assertEqual(pe.INCOMPLET, [(2026, "QUESTION_WRITTEN")])

    def test_500_passager_ne_coupe_pas_la_pagination(self):
        """Deux pages pleines, un 500 au milieu : la liste doit être entière."""
        self.repond(self.page(pe.PAR_PAGE), erreur(500),
                    self.page(pe.PAR_PAGE, pe.PAR_PAGE), self.page(2))
        obtenus = pe.identifiants(2026, "QUESTION_WRITTEN")
        self.assertEqual(len(obtenus), pe.PAR_PAGE * 2 + 2)
        self.assertEqual(pe.INCOMPLET, [])

    def test_204_termine_proprement(self):
        """La pagination qui dépasse la dernière page ne doit pas lever."""
        self.repond(self.page(pe.PAR_PAGE), Reponse(b"", status=204))
        self.assertEqual(len(pe.identifiants(2026, "QUESTION_WRITTEN")), pe.PAR_PAGE)
        self.assertEqual(pe.INCOMPLET, [])


if __name__ == "__main__":
    unittest.main()
