# Étude de faisabilité — octobre 2026

Les débats de l'Assemblée nationale, du Sénat et du Parlement européen permettent
de suivre ce que disent les élu·es français·es sur l'IA. Aucun·e n'y évoque les
risques extrêmes (superintelligence, AGI, risque existentiel) en séance publique
depuis juillet 2024 ; on en trouve en revanche dans les questions écrites.

## Sources testées

Période : juillet 2024 au 14 octobre 2026, séance publique uniquement.

| Source | Accès | Délai | Passages sur l'IA | Orateurs | Risques extrêmes |
| --- | --- | --- | --- | --- | --- |
| [Assemblée nationale](https://data.assemblee-nationale.fr/travaux-parlementaires/debats) | Téléchargement d'une archive ZIP (55 Mo, XML) | 1 jour | 448 paragraphes | 217 | 0 |
| [Sénat](https://www.data.gouv.fr/datasets/comptes-rendus-du-senat/informations) | Téléchargement d'une archive ZIP (545 Mo depuis 2003, HTML) | ~1 semaine | 584 interventions | 200 | 0 |
| [Parlement européen](https://data.europarl.europa.eu/api/v2/) (81 élu·es FR) | API publique avec recherche plein texte | Quelques jours | 69 interventions | 32 | 0 |

Chaque orateur porte son identifiant officiel (`id_acteur` à l'AN, matricule au
Sénat, identifiant PE), ce qui permet de le rattacher sans ambiguïté à une fiche.

## Mots-clés

La liste complète est dans `scripts/exploration/motscles.py`, en cinq familles :

- **Pré-filtre** : « intelligence artificielle », « IA », « artificial intelligence »
  (et le sigle « AI » dans les titres du PE). « IA-IPR » est exclu.
- **Risques extrêmes** : superintelligence, IA générale, AGI, extinction,
  singularité technologique, AI 2027 ; auto-amélioration, risque existentiel,
  perte de contrôle (ou de maîtrise, de supervision).
- **Sécurité et gouvernance de l'IA** : sécurité ou sûreté de l'IA, alignement,
  moratoire ou pause, ralentissement, contrôle humain, tests avant déploiement,
  modèles de frontière, risque systémique, instituts de sécurité (INESIA,
  AI Safety Institute, Bletchley), armes autonomes, SALA.
- **Entreprises et produits** : OpenAI / ChatGPT, Anthropic, Claude, Mistral,
  DeepMind / Gemini, xAI / Grok, Llama, DeepSeek.
- **Personnalités** : Maxime Fournes, Yoshua Bengio, Geoffrey Hinton,
  Stuart Russell, Sam Altman, Dario Amodei, Demis Hassabis, Yann LeCun,
  Arthur Mensch, Jacob Coxon, Daniel Kokotajlo, Jan Leike,
  Leopold Aschenbrenner, Steven Adler.
- **Organisations** : Pause IA, CeSIA, Future of Life Institute,
  Center for AI Safety.

Les mots ambigus ne comptent que **à moins de 300 caractères d'une mention de
l'IA** : seuls, « perte de contrôle » ou « moratoire » renvoyaient à l'Ukraine, à
la sidérurgie ou aux finances publiques. Les sigles sont cherchés en majuscules
exactes et jamais collés à un tiret (« agi » est un participe passé, « AGI-SON »
une association). « IAG » a été retiré : il désigne le plus souvent l'IA
*générative*. Recherche insensible à la casse et aux accents, sauf pour les sigles.

## Pièges rencontrés

- **AN** : la présidence de séance n'est pas toujours marquée `roledebat="president"` ;
  elle est aussi exclue par son libellé. Les comptes rendus provisoires sont
  régénérés quand ils sont corrigés.
- **Sénat** : HTML non strict (lu avec `html.parser`), encodage variable
  (ISO-8859-1 ou UTF-8), un fichier daté du 4 décembre 2026 (coquille probable
  pour 2025). Une intervention peut faire plusieurs pages : « parle d'IA dans la
  même intervention » est trop large, il faudra exiger la proximité.
- **PE** : les textes et leurs métadonnées arrivent dans deux listes d'ordre
  différent, à joindre par identifiant. 36 textes sur 69 sont marqués
  `fr-t-en-mtec` alors que l'élu·e a parlé français : probablement une
  transcription automatique, à vérifier avant toute citation.

## Questions écrites (ajout du 15/10/2026)

Les questions écrites sont la source la plus riche : les élu·es y développent
leur position sur plusieurs paragraphes, alors qu'en séance l'IA n'est souvent
qu'évoquée au passage.

| Source | Données | Ce qu'on analyse | Période | Script |
|---|---|---|---|---|
| AN | `an-questions.zip` (JSON) | résumé et texte | 17e législature | `explore_an_questions.py` |
| Sénat | `senat-questions.csv`, puis la page de chaque question retenue | titre, puis texte complet | 16/10/2025 → 15/10/2026 | `explore_senat_questions.py`, `textes_senat_questions.py` |
| PE | dump Parltrack (`parltrack-activities.json.zst`) | titre seulement (en anglais) | 17/09/2024 → 15/07/2026 | `explore_pe_questions.py` |

### Pièges rencontrés

- **AN** : un élément seul est un objet JSON, plusieurs éléments une liste
  (fonction `premier()`). Le fichier ne donne que l'identifiant de l'auteur : on
  lit son nom au début du texte (« M. X interroge… »), d'où une liste de verbes
  à compléter (`interpelle`, `expose`… manquaient).
- **Titre de la ministre** : les questions adressées à la « ministre déléguée
  chargée de l'intelligence artificielle et du numérique » contiennent toutes
  « intelligence artificielle ». Ce titre est effacé avant la détection, sinon
  toute question sur le numérique (2G, quantique…) compte comme parlant d'IA.
- **Sénat** : le CSV est en iso-8859-1 avec des « ; ». Il ne contient que les
  titres : le texte complet est récupéré sur senat.fr, avec une pause d'une
  seconde entre deux pages.
- **PE** : l'API officielle ne donne ni titre ni texte, et les pages doceo sont
  interdites aux robots (robots.txt). On passe par Parltrack, qui s'arrête au
  24/07/2026. Les titres étant en anglais, le sigle « AI » est traduit avant
  l'analyse. Les questions cosignées apparaissent sous chaque auteur.

### Résultats

| Source | Questions lues | Retenues | Auteur·ices |
|---|---|---|---|
| AN | 19 009 | 300 | 172 |
| Sénat | 5 081 | 31 | 17 |
| PE | 4 078 | 65 | 29 |

Contrairement aux séances, on trouve ici des **risques extrêmes** : perte de
contrôle (Antoine Villedieu à l'AN, Hugues Saury au Sénat) et IA générale
(René Pilato à l'AN). Rien de tel dans les titres du PE.

## Synthèse par élu·e

`synthese.py` fusionne tous les `passages_*.csv` et écrit `synthese_elus.csv`
(séparateur « ; », UTF-8 avec BOM pour Excel) : une ligne par personne, avec
chambre, groupe, nombre de passages, mots-clés par famille, dates, extrait le
plus pertinent et lien.

- Les textes sont **ré-analysés** avec `motscles.py` : une correction des
  mots-clés s'applique à toutes les sources sans relancer chaque script.
- Regroupement par chambre et par nom normalisé (sans accents, casse ni
  civilité).
- **Gouvernement** : repéré automatiquement, par la qualité de l'orateur à l'AN
  (« ministre », « garde des sceaux »…) et par l'attribut `type="2"` au Sénat.
  Chaque intervention est classée selon le rôle tenu ce jour-là : un·e
  parlementaire devenu·e ministre a deux lignes.
- **Personnalités auditionnées** : invité·es extérieur·es, repéré·es par leur
  identifiant avec tiret à l'AN (`PA-125909`) et par un type d'intervenant
  autre que 1 ou 2 au Sénat ; ils sont rangés à part.
- Garde-fou : un « nom » de plus de 60 caractères est signalé et écarté.

### Score

Chaque passage rapporte le poids de son mot-clé le plus fort, plus 1 point par
passage sur l'IA (plafonné à 10).

| Famille | Poids |
|---|---|
| Risques extrêmes | 10 |
| Organisations de la sécurité de l'IA | 8 |
| Sécurité et gouvernance de l'IA | 5 |
| Personnalités | 4 |
| Entreprises et produits | 1 |

Ajustements : « contrôle humain » 2, Sam Altman 2, Arthur Mensch 1, Yann LeCun 1.
Ces poids sont à valider avec l'équipe plaidoyer.

Version du 15/10/2026 : 514 personnes, dont 245 député·es, 170 sénateur·ices,
47 eurodéputé·es, 48 membres du gouvernement et 4 personnalités auditionnées.

### Limites et suite

- Questions du Sénat : un an d'historique seulement.
- Questions du PE : titres seulement, et rien depuis mi-juillet 2026.
- Le tri par mots-clés reste un premier filtre : une seconde passe par LLM
  (clé à venir) permettrait de qualifier la position de chaque élu·e.

## Conclusions

- Pas de blocage comme aux États-Unis : sources gratuites, fraîches, orateurs identifiés.
- Environ 45 passages sur l'IA par mois au total : assez peu pour une relecture
  humaine ou une classification par LLM.
- Les mots-clés trient bien mais ne jugent pas le ton : en séance, le passage
  le plus pertinent (Marie-Claire Carrère-Gée, Sénat, 28 avril 2025, sur les
  risques de l'IA générative) ne se repère qu'en lisant.
- Les questions écrites sont la meilleure source pour repérer les élu·es
  sensibles aux risques : c'est là qu'apparaissent la perte de contrôle et
  l'IA générale.

## Pistes pour la suite

| Source | Ce qu'il faudrait |
| --- | --- |
| Seconde passe par LLM sur les passages déjà extraits | Repérer ce que les mots-clés ratent ; classer thème, ton, sensibilité aux risques |
| Comptes rendus de commission | Mesurer leur délai de publication |
| Tricoteuses (données parlementaires nettoyées) | Les contacter pour leur API, qui éviterait aussi de retélécharger l'archive du Sénat |
| Flux RSS des médias, GDELT | Rattacher chaque article au bon élu·e ; ne garder que le lien et un extrait |
| Réseaux sociaux | API de X payante ; Bluesky et Mastodon ouverts |
| Dépêches AFP | Un abonnement, et un contrat autorisant le traitement automatisé |

Point d'attention budget : la presse et certaines API sont payantes et peuvent
changer de conditions ou fermer. Priorité aux sources officielles gratuites.
