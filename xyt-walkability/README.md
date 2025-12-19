
# xyt-walkability

Pipeline ETL modulaire pour le calcul de l’indice de marchabilité (walkability index) à partir de réseaux piétons, prêt pour la production, la recherche et la publication PyPI.

---

## 🚀 Installation

```bash
git clone <repo-url>
cd xyt-walkability
pip install -e .  # mode développement
# ou
pip install .     # mode standard
```

---

## 🖥️ Utilisation CLI

Chaque étape du pipeline est accessible via la CLI :

```bash
# Extraction et préparation du réseau piéton (étape 0)
xyt-walkability prepare-network \
	--input "Canton de Genève, Switzerland" \
	--output data/output/step-1 \
	--crs EPSG:2056

# Calcul des attributs/features (étape 1)
xyt-walkability prepare-features \
	--input data/output/step-1/network_edges.geojson \
	--output data/output/step-2 \
	--attributs-info data/input/attributs/attributs_info.xlsx

# Filtrage/validation (étape 2)
xyt-walkability filter-features \
	--input data/output/step-2/features_enriched.geojson \
	--output data/output/step-2b \
	--formats geojson gpkg parquet

# Agrégation et calcul de l’indice (étape 3)
xyt-walkability aggregate-index \
	--input data/output/step-2b/features_filtered.geojson \
	--output data/output/step-3 \
	--zones-girec data/input/zones_girec.gpkg \
	--agglo-carreau data/input/carreau200.gpkg
```

---

## 🐍 Utilisation API Python

Chaque étape est accessible en Python :

```python
from xyt.walkability.prepare_network import prepare_network
from xyt.walkability.prepare_features import prepare_features
from xyt.walkability.filter_features import filter_features
from xyt.walkability.aggregate_index import aggregate_index

# Exemple : segmentation du réseau
prepare_network(
	input_path="Canton de Genève, Switzerland",
	output_path="data/output/step-1",
	params={"crs": "EPSG:2056"}
)

# Exemple : enrichissement des features
prepare_features(
	input_path="data/output/step-1/network_edges.geojson",
	output_path="data/output/step-2",
	params={"attributs_info": "data/input/attributs/attributs_info.xlsx"}
)
```

---

## 🛠️ Personnalisation & Configuration

- Tous les paramètres sont passés via `params` (API) ou options CLI.
- Les formats de sortie supportés : GeoJSON, GPKG, Parquet, CSV.
- L’étape 2 (filtrage) peut être manuelle (édition dans QGIS, notebook, etc.).
- Voir les docstrings de chaque fonction pour la liste complète des options.

---

## 🔄 Pipeline complet (exemple)

```bash
xyt-walkability prepare-network --input "Canton de Genève, Switzerland" --output data/output/step-1
xyt-walkability prepare-features --input data/output/step-1/network_edges.geojson --output data/output/step-2 --attributs-info data/input/attributs/attributs_info.xlsx
# (optionnel) édition manuelle des features
xyt-walkability filter-features --input data/output/step-2/features_enriched.geojson --output data/output/step-2b --formats geojson gpkg
xyt-walkability aggregate-index --input data/output/step-2b/features_filtered.geojson --output data/output/step-3 --zones-girec data/input/zones_girec.gpkg --agglo-carreau data/input/carreau200.gpkg
```

---

## 🤝 Contribution

Les contributions sont les bienvenues ! Merci de :
- Respecter la structure modulaire (un fichier par étape)
- Ajouter des tests si possible (`pytest`)
- Documenter toute nouvelle fonctionnalité

---

## ❓ Support & Dépannage

- Consultez les messages d’erreur pour les fichiers manquants ou formats non supportés.
- Vérifiez la présence des dépendances dans `requirements.txt`.
- Pour toute question, ouvrez une issue sur le dépôt.

---

## 📄 Licence

MIT
