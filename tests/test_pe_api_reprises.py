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
        pe.ILLISIBLES.clear()
        self.vrai_stderr, sys.stderr = sys.stderr, io.StringIO()

    def tearDown(self):
        reseau.urllib.request.urlopen = self.vrai_urlopen
        reseau.time.sleep = self.vrai_sleep
        sys.stderr = self.vrai_stderr
        pe.INCOMPLET.clear()
        pe.ILLISIBLES.clear()

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
        """API en panne (ni la page ni aucun morceau ne passe) : on garde les
        100 premiers identifiants plutôt que rien du tout, et on le signale."""
        morceaux_en_echec = [erreur(500)] * (pe.ESSAIS_MORCEAU * (pe.PAR_PAGE // pe.MORCEAU))
        self.repond(self.page(pe.PAR_PAGE),
                    *[erreur(500)] * reseau.ESSAIS, *morceaux_en_echec)
        obtenus = pe.identifiants(2026, "QUESTION_WRITTEN")
        self.assertEqual(len(obtenus), pe.PAR_PAGE)
        self.assertEqual(pe.INCOMPLET, [(2026, "QUESTION_WRITTEN")])
        self.assertEqual(pe.ILLISIBLES, [])

    def test_une_question_illisible_ne_coupe_plus_la_liste(self):
        """Le cas du 26/10/2026 : la page de la 2 001e question écrite répond
        toujours 500, la suivante répond bien. On ne doit perdre que la question
        fautive, pas toutes celles qui suivent."""
        P, M = pe.PAR_PAGE, pe.MORCEAU
        suite = [self.page(P)]                                  # page 0 : bonne
        suite += [erreur(500)] * reseau.ESSAIS                  # page 1 : en échec
        suite += [self.page(M, P)]                              # morceau 100-109
        suite += [erreur(500)] * pe.ESSAIS_MORCEAU              # morceau 110-119 : en échec
        suite += [self.page(M, P + d) for d in range(2 * M, P, M)]  # morceaux 120-199
        # Le morceau 110-119 relu question par question : la 114 est fautive.
        for position in range(P + M, P + 2 * M):
            if position == P + M + 4:
                suite += [erreur(500)] * pe.ESSAIS_MORCEAU
            else:
                suite.append(self.page(1, position))
        suite.append(self.page(2, 2 * P))                       # page 2 : fin de liste
        self.repond(*suite)
        obtenus = pe.identifiants(2026, "QUESTION_WRITTEN")
        self.assertEqual(len(obtenus), 2 * P + 2 - 1)           # tout sauf la fautive
        self.assertNotIn(f"Q-{P + M + 4}", obtenus)
        self.assertIn(f"Q-{2 * P + 1}", obtenus)                # la suite est bien lue
        self.assertEqual(obtenus, sorted(obtenus, key=lambda q: int(q[2:])))  # ordre gardé
        self.assertEqual(pe.ILLISIBLES, [(2026, "QUESTION_WRITTEN", P + M + 4)])
        self.assertEqual(pe.INCOMPLET, [])

    def test_fin_de_liste_dans_une_page_relue(self):
        """La page en échec est la dernière : le morceau incomplet clôt la liste."""
        P, M = pe.PAR_PAGE, pe.MORCEAU
        self.repond(self.page(P), *[erreur(500)] * reseau.ESSAIS,
                    self.page(M, P), self.page(3, P + M))
        obtenus = pe.identifiants(2026, "QUESTION_WRITTEN")
        self.assertEqual(len(obtenus), P + M + 3)
        self.assertEqual(pe.INCOMPLET, [])

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



class TestFiche(SansReseau):
    def test_le_format_json_est_demande(self):
        """Sans `format`, l'API rend certaines fiches en XML (constaté le 26/10/2026)."""
        faux = self.repond(Reponse(
            b'{"data": [{"document_date": "2026-10-20T00:00:00", '
            b'"creator": ["person/94649"], "title_dcterms": {"fr": "IA et emploi"}}]}'))
        adresses = []
        vrai = faux.__call__

        def espion(requete, timeout=None):
            adresses.append(requete.full_url)
            return vrai(requete, timeout)

        reseau.urllib.request.urlopen = espion
        q = pe.fiche("E-10-2026-000047")
        self.assertIn("format=application%2Fld%2Bjson", adresses[0])
        self.assertEqual(q, {"date": "2026-10-20", "auteurs": ["94649"],
                             "titre": "IA et emploi"})

if __name__ == "__main__":
    unittest.main()
