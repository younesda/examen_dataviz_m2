# Younes Hachami Dataviz

Plateforme de data visualisation multi-sectorielle construite avec Flask, Dash, Plotly et MongoDB.
Le projet regroupe trois volets metier:

- Banking (`/dashboard.html`): tableau de bord statique HTML/JS analysant le secteur bancaire senegalais (2015-2022). Filtres annee, groupe et banque — annee defaut sur "Toutes". Exports PDF, CSV et Excel.
- Solar (`/solar/`): suivi de performance telemetrique AC/DC, irradiation, temperatures et yield par pays. Exports CSV et Excel des donnees filtrees.
- Insurance (`/insurance/`): analyse de portefeuille primes, sinistres, loss ratio, rentabilite avec navigation par page. Exports CSV et Excel via Dash Download.

## Points forts

- Application web unique avec navigation Flask et dashboards Dash specialises
- Pipeline de preprocessing separe pour les donnees banking, solar et insurance
- Chargement MongoDB avec logique de reprise et fallback local pour le solaire
- Exports de donnees sur tous les dashboards: PDF (banking), CSV et Excel (banking, solar, insurance)

## Stack technique

- Python 3.13
- Flask
- Dash + Plotly + Dash Bootstrap Components
- Pandas + NumPy
- MongoDB / PyMongo
- html2pdf.js (export PDF banking)
- SheetJS xlsx.js (export Excel banking et solar)
- pdfplumber + ReportLab

## Structure du depot

```text
.
|-- app.py                        # Point d'entree Flask + montage des dashboards Dash
|-- assets/
|   |-- style.css                 # Styles globaux et insurance dashboard
|   |-- solar_observatory.css     # Styles solar
|   `-- solar_observatory.js      # Logique solar (filtres, charts, exports CSV/Excel)
|-- dashboards/
|   |-- dashboard.html            # Dashboard banking HTML/JS standalone
|   |-- banking_dashboard.py      # Dashboard banking Dash (KPI avances)
|   |-- insurance_dashboard.py    # Dashboard insurance Dash multipage
|   `-- solar_page.py             # Page solar rendue via Flask template
|-- database/
|-- preprocessing/
|   |-- data_bank/
|   |-- insurance_data/
|   |-- solar_data/
|   |-- database/
|   |-- scripts/
|   `-- README.md
|-- requirements.txt
`-- CONTRIBUTING.md
```

## Demarrage rapide

### 1. Creer un environnement virtuel

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 2. Configurer les variables d'environnement

Copier `.env.example` comme base ou definir les variables directement dans PowerShell:

```powershell
$env:HOST="127.0.0.1"
$env:PORT="8050"
$env:DASH_DEBUG="false"
$env:MONGO_URI="<ta-chaine-mongodb>"
$env:PROJECT_GITHUB_URL="https://github.com/<user>/<repo>"
```

Variables prises en charge:

- `HOST`: hote du serveur Flask local
- `PORT`: port d'exposition de l'application
- `DASH_DEBUG`: active le mode debug si `true`
- `MONGO_URI`: chaine de connexion MongoDB pour l'application web
- `PROJECT_GITHUB_URL`: lien affiche sur la page d'accueil

## Lancer l'application web

```powershell
python app.py
```

L'application demarre par defaut sur `http://127.0.0.1:8050`.

## Lancer le pipeline de preprocessing / ingestion

Preprocessing + ingestion MongoDB:

```powershell
python .\preprocessing\scripts\ingest_data.py --log-level INFO
```

Preprocessing seul:

```powershell
python .\preprocessing\scripts\ingest_data.py --skip-mongo --log-level INFO
```

## Donnees et conventions

- Les donnees sources versionnees vivent sous `preprocessing/data_bank`, `preprocessing/insurance_data` et `preprocessing/solar_data`.
- Ne pas committer de fichiers de debug, logs, captures ou exports temporaires.
- Si les datasets binaires deviennent plus lourds, envisager Git LFS plutot que de versionner de gros fichiers bruts directement.

## Workflow Git recommande

1. Creer une branche courte et explicite.
2. Faire des commits atomiques avec un message clair.
3. Verifier manuellement l'application et le pipeline avant tout push.
4. Ouvrir une pull request avec un resume clair des impacts.

Style de messages conseille:

- `feat: ajouter une vue banking par groupe`
- `fix: corriger le fallback mongo`
- `docs: clarifier l'installation`
- `chore: nettoyer le depot`

## Fichiers de collaboration ajoutes

- `CONTRIBUTING.md`: regles de contribution
- `.editorconfig`: style de base partage
- `.gitattributes`: normalisation line endings et types binaires
- `.github/ISSUE_TEMPLATE/*` et `.github/PULL_REQUEST_TEMPLATE.md`: trames de collaboration

## Note de securite

Pour garder un depot sain, privilegie toujours des variables d'environnement locales pour MongoDB et ne committe jamais de secrets, exports prives ou logs d'execution.

## Documentation complementaire

La documentation du pipeline de preprocessing est disponible dans `preprocessing/README.md`.
