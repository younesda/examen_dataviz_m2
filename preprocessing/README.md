# Preprocessing Pipeline - Phase 1

## Objectif
Cette documentation resume la phase 1 du projet Data Visualization construit avec Dash + Flask + MongoDB.
L'objectif est de nettoyer, normaliser, enrichir puis ingerer les donnees dans MongoDB Atlas.

## Sources de donnees
- Banking: `project_dataviz/data_bank/BASE_SENEGAL2.xlsx`
- BCEAO PDF: `project_dataviz/data_bank/bilans_bceao.pdf`
- Solar: `project_dataviz/solar_data/solar_dataset.csv`
- Insurance: `project_dataviz/insurance_data/insurance_dataset.csv`

## Structure implemente
- `project_dataviz/scripts/preprocessing_bank.py`
- `project_dataviz/scripts/preprocessing_solar.py`
- `project_dataviz/scripts/preprocessing_insurance.py`
- `project_dataviz/database/mongo_connection.py`
- `project_dataviz/scripts/ingest_data.py`

## Pipeline bancaire
Le preprocessing bancaire combine deux sources:
- le fichier Excel comme schema officiel
- le PDF BCEAO comme source complementaire pour les banques du Senegal

### Banques ciblees
- CBAO
- SGBS
- ECOBANK SENEGAL
- BICIS
- ORABANK
- BANK OF AFRICA SENEGAL
- CORIS BANK
- UBA SENEGAL
- BSIC SENEGAL
- BNDE
- BHS

### Regles metier appliquees
- normalisation des noms de colonnes en `snake_case`
- conversion des montants BCEAO de millions FCFA vers FCFA
- fusion sur `sigle + annee`
- enrichissement avec:
  - `ratio_fonds_propres`
  - `ratio_ressources`
  - `rentabilite`
- conservation de la provenance via:
  - `source_excel`
  - `source_pdf`
  - `record_origin`

### Equivalences Excel / PDF prises en charge
Le pipeline fusionne maintenant les colonnes principales et les colonnes detaillees de compte de resultat:
- `emploi`
- `bilan`
- `ressources`
- `fonds_propres`
- `interets_et_produits_assimiles`
- `interets_et_charges_assimilees`
- `revenus_des_titres_a_revenu_variable`
- `commissions_produits`
- `commissions_charges`
- `gains_ou_pertes_nets_sur_operations_des_portefeuilles_de_negociation`
- `gains_ou_pertes_nets_sur_operations_des_portefeuilles_de_placement_et_assimiles`
- `autres_produits_d_exploitation_bancaire`
- `autres_charges_d_exploitation_bancaire`
- `produit_net_bancaire`
- `subventions_d_investissement`
- `charges_generales_d_exploitation`
- `dotations_aux_amortissements_et_aux_depreciations_des_immobilisations_incorporelles_et_corporelles`
- `resultat_brut_d_exploitation`
- `cout_du_risque`
- `resultat_exploitation`
- `gains_ou_pertes_nets_sur_actifs_immobilises`
- `resultat_avant_impot`
- `impots_sur_les_benefices`
- `resultat_net`

### Qualite des donnees
Sur les lignes communes Excel + PDF, les colonnes equivalentes fusionnees ne contiennent pas de valeurs nulles pour les champs repris par le PDF.

## Pipeline solar
Le fichier fourni est un dataset meteorologique. Le pipeline:
- convertit la date
- nettoie les colonnes
- supprime les lignes invalides
- calcule `production_efficiency`
- calcule `annual_growth`

Note: comme il n'y a pas de colonne explicite de production solaire, `production_efficiency` est calcule via un proxy meteorologique documente dans le code.

## Pipeline insurance
Le pipeline:
- supprime les doublons
- convertit les colonnes numeriques
- normalise les categories
- calcule `premiums`, `claims`, `profit`
- calcule `loss_ratio`
- calcule `profit_margin`

## MongoDB
Base cible:
- `bank_dataviz`

Collections:
- `banking_data`
- `solar_energy_data`
- `insurance_data`

## Execution
Commande principale:

```bash
python .\project_dataviz\scripts\ingest_data.py --log-level INFO
```

Execution sans insertion MongoDB:

```bash
python .\project_dataviz\scripts\ingest_data.py --skip-mongo --log-level INFO
```

## Resultat de la phase 1
Le pipeline preprocess les trois datasets et les charge dans MongoDB Atlas avec une logique modulaire, commentee et robuste pour alimenter les dashboards Dash.
