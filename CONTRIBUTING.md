# Contributing

Merci de contribuer au projet.
L'objectif de ce document est de garder un depot simple a maintenir, lisible et stable.

## Workflow recommande

1. Synchroniser ta branche locale avec `main`.
2. Creer une branche courte et explicite.
3. Developper par petits commits atomiques.
4. Verifier manuellement l'application ou le pipeline avant de pousser.
5. Ouvrir une pull request avec un resume clair.

## Conventions de branches

Exemples conseilles:

- `feat/banking-kpi`
- `fix/mongo-fallback`
- `docs/readme`
- `chore/repo-cleanup`

## Conventions de commits

Utiliser des messages explicites, par exemple:

- `feat: ajouter une page assurance`
- `fix: corriger le chargement mongo`
- `docs: enrichir le readme`
- `chore: nettoyer les artefacts locaux`

## Qualite attendue

- Toute nouvelle variable d'environnement doit etre documentee dans `README.md` et `.env.example`.
- Toute modification de pipeline de donnees doit mentionner les datasets impactes.
- Ne pas committer de logs, caches, captures d'ecran ou exports locaux.

## Checklist avant pull request

- L'application ou le pipeline a ete verifie localement
- Les changements sont scopes a un objectif clair
- La documentation a ete mise a jour si necessaire
- Aucun secret ou artefact local n'est versionne

## Pull requests

Une bonne PR contient:

- le contexte du changement
- la solution retenue
- les fichiers ou zones impactes
- les verifications effectuees
- les points a relire en priorite
