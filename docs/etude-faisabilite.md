# Étude de faisabilité — octobre 2026

Les débats de l'Assemblée nationale, du Sénat et du Parlement européen permettent
de suivre ce que disent les élu·es français·es sur l'IA. En revanche, aucun·e n'y
évoque les risques extrêmes (superintelligence, AGI, risque existentiel) en séance
publique depuis juillet 2024.

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

- **Pré-filtre** : « intelligence artificielle », « IA » (« artificial intelligence » au PE).
- **Risques extrêmes** : superintelligence, IA générale, AGI, IAG, extinction de
  l'humanité, singularité technologique, auto-amélioration, Pause IA.
- **Seulement si le passage parle d'IA** : « risque existentiel », « perte de contrôle ».
  Seuls, ils renvoyaient à l'Ukraine, à la sidérurgie ou aux finances publiques.
- **Sigles en majuscules exactes, jamais collés à un tiret** : « agi » est un
  participe passé, « AGI-SON » une association.

Recherche insensible à la casse et aux accents, sauf pour les sigles.

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

## Conclusions

- Pas de blocage comme aux États-Unis : sources gratuites, fraîches, orateurs identifiés.
- Environ 45 passages sur l'IA par mois au total : assez peu pour une relecture
  humaine ou une classification par LLM.
- Les mots-clés trient bien mais ne jugent pas le ton : le seul passage pertinent
  (Marie-Claire Carrère-Gée, Sénat, 28 avril 2025, sur les risques de l'IA
  générative) ne se repère qu'en lisant.

## Pistes pour la suite

| Source | Ce qu'il faudrait |
| --- | --- |
| Seconde passe par LLM sur les passages déjà extraits | Repérer ce que les mots-clés ratent ; classer thème, ton, sensibilité aux risques |
| Questions écrites (AN, Sénat, PE) | Open data et API disponibles : à tester en priorité |
| Comptes rendus de commission | Mesurer leur délai de publication |
| Tricoteuses (données parlementaires nettoyées) | Les contacter pour leur API, qui éviterait aussi de retélécharger l'archive du Sénat |
| Flux RSS des médias, GDELT | Rattacher chaque article au bon élu·e ; ne garder que le lien et un extrait |
| Réseaux sociaux | API de X payante ; Bluesky et Mastodon ouverts |
| Dépêches AFP | Un abonnement, et un contrat autorisant le traitement automatisé |

Point d'attention budget : la presse et certaines API sont payantes et peuvent
changer de conditions ou fermer. Priorité aux sources officielles gratuites.
