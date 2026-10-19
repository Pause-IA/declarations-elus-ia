"""Les reprises sur l'API du Parlement européen, et la fin de liste.

Le 19/10/2026 l'API a renvoyé « HTTP 500 » environ une fois sur cinq, de façon
intermittente : la même adresse demandée cinq fois a répondu quatre fois 200 et
une fois 500. Le script, sans aucune reprise, a fait échouer tout le passage
quotidien — alors que les cinq autres sources étaient en bon état. Ces cas
figent le comportement attendu.
"""
import io
import os
import sys
import unittest
import urllib.error

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "scripts", "exploration"))

import explore_pe_questions_api as pe  # noqa: E402


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


class TestLireJson(unittest.TestCase):
    def setUp(self):
        self.vrai_urlopen = pe.urllib.request.urlopen
        self.vrai_sleep = pe.time.sleep
        pe.time.sleep = lambda _: None          # pas d'attente réelle dans les tests
        pe.INCOMPLET.clear()
        self.err = io.StringIO()
        self.vrai_stderr, sys.stderr = sys.stderr, self.err

    def tearDown(self):
        pe.urllib.request.urlopen = self.vrai_urlopen
        pe.time.sleep = self.vrai_sleep
        sys.stderr = self.vrai_stderr
        pe.INCOMPLET.clear()

    def test_500_passager_puis_succes(self):
        """Le cas réel : un 500 isolé ne doit plus rien casser."""
        reseau = FauxReseau(erreur(500), Reponse(b'{"data": []}'))
        pe.urllib.request.urlopen = reseau
        self.assertEqual(pe.lire_json("http://x"), {"data": []})
        self.assertEqual(reseau.appels, 2)

    def test_plusieurs_500_de_suite(self):
        reseau = FauxReseau(erreur(500), erreur(503), erreur(500),
                            Reponse(b'{"data": [1]}'))
        pe.urllib.request.urlopen = reseau
        self.assertEqual(pe.lire_json("http://x"), {"data": [1]})
        self.assertEqual(reseau.appels, 4)

    def test_429_est_reessaye(self):
        reseau = FauxReseau(erreur(429), Reponse(b"{}"))
        pe.urllib.request.urlopen = reseau
        self.assertEqual(pe.lire_json("http://x"), {})

    def test_abandon_apres_toutes_les_tentatives(self):
        reseau = FauxReseau(*[erreur(500)] * pe.ESSAIS)
        pe.urllib.request.urlopen = reseau
        with self.assertRaises(urllib.error.HTTPError):
            pe.lire_json("http://x")
        self.assertEqual(reseau.appels, pe.ESSAIS)

    def test_404_ne_est_pas_reessaye(self):
        """Une erreur de notre requête : la réessayer ne sert à rien."""
        reseau = FauxReseau(erreur(404), Reponse(b"{}"))
        pe.urllib.request.urlopen = reseau
        with self.assertRaises(urllib.error.HTTPError):
            pe.lire_json("http://x")
        self.assertEqual(reseau.appels, 1)

    def test_204_est_une_fin_de_liste(self):
        """204 No Content : pas une erreur, le corps est simplement vide."""
        pe.urllib.request.urlopen = FauxReseau(Reponse(b"", status=204))
        self.assertEqual(pe.lire_json("http://x"), {})

    def test_corps_vide_en_200(self):
        pe.urllib.request.urlopen = FauxReseau(Reponse(b"   "))
        self.assertEqual(pe.lire_json("http://x"), {})


class TestIdentifiants(unittest.TestCase):
    def setUp(self):
        self.vrai_urlopen = pe.urllib.request.urlopen
        self.vrai_sleep = pe.time.sleep
        pe.time.sleep = lambda _: None
        pe.INCOMPLET.clear()
        self.err = io.StringIO()
        self.vrai_stderr, sys.stderr = sys.stderr, self.err

    def tearDown(self):
        pe.urllib.request.urlopen = self.vrai_urlopen
        pe.time.sleep = self.vrai_sleep
        sys.stderr = self.vrai_stderr
        pe.INCOMPLET.clear()

    def page(self, combien, depart=0):
        corps = b'{"data": [' + b", ".join(
            b'{"identifier": "Q-%d"}' % (depart + i) for i in range(combien)) + b"]}"
        return Reponse(corps)

    def test_une_page_incomplete_arrete_la_pagination(self):
        pe.urllib.request.urlopen = FauxReseau(self.page(3))
        self.assertEqual(pe.identifiants(2026, "QUESTION_WRITTEN"),
                         ["Q-0", "Q-1", "Q-2"])
        self.assertEqual(pe.INCOMPLET, [])

    def test_page_en_echec_rend_une_liste_partielle(self):
        """Mieux vaut les 100 premiers identifiants que rien du tout."""
        pleine = self.page(pe.PAR_PAGE)
        pe.urllib.request.urlopen = FauxReseau(pleine, *[erreur(500)] * pe.ESSAIS)
        obtenus = pe.identifiants(2026, "QUESTION_WRITTEN")
        self.assertEqual(len(obtenus), pe.PAR_PAGE)
        self.assertEqual(pe.INCOMPLET, [(2026, "QUESTION_WRITTEN")])

    def test_204_termine_proprement(self):
        """La pagination qui dépasse la dernière page ne doit pas lever."""
        pe.urllib.request.urlopen = FauxReseau(self.page(pe.PAR_PAGE),
                                               Reponse(b"", status=204))
        self.assertEqual(len(pe.identifiants(2026, "QUESTION_WRITTEN")), pe.PAR_PAGE)
        self.assertEqual(pe.INCOMPLET, [])


if __name__ == "__main__":
    unittest.main()
