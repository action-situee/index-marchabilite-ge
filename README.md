
<p align="center">
  <img src="https://assets.super.so/15749c3c-d748-4e49-bff7-6fc9ec745dc4/images/5a6a8136-ad7e-4071-861d-5cff2b4ff8f3/Fichier_36.svg" alt="Logo" width="200"/>
</p>

# 📌 Projet marchabilité

## 🚨 Règles importantes avant de commencer

Merci de respecter ces règles essentielles pour garantir la propreté du dépôt :

- **Aucune donnée (même légère) ne doit être poussée sur GitHub.**
  - Les fichiers de données doivent être placés dans le dossier `Data/`, qui est ignoré grâce au `.gitignore`.
  - Cela inclut les jeux de données CSV, Excel, JSON, etc.

- **Aucun fichier trop lourd (supérieur à 50 Mo) ne doit être ajouté.**

- **Les notebooks (`.ipynb`) doivent être nettoyés avant push :**
  - Supprimer les outputs et checkpoints.
  - S'assurer qu'ils restent lisibles et légers.

En cas de doute, demandez de l’aide avant de faire un push !

---

## 📖 Description
Ce projet vise à implémenter un indice spatial de marchabilité sur l'ensemble du territoire cantonal.

---

## 🛠 Contribution

Merci de suivre le guide de contribution (`CONTRIBUTING.md`) et le workflow Git (`WORKFLOW.md`).

---

## 🛠️ Environnement de travail recommandé

- **Python 3.11.0**
- **Visual Studio Code (VSCode)** avec :
  - Extension **Jupyter** pour ouvrir et exécuter des notebooks `.ipynb`.
  - Extension **Git** pour la gestion de version.
  - **GitHub Copilot** (gratuit avec le compte EPFL) pour l’assistance intelligente au code.

### Installation de l’environnement virtuel (Mac)
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

🔔 **Remarque :** Sur Windows, l’activation du venv se fait avec :
```bash
venv\Scripts\activate
```

⚡ Activez le venv à chaque session de travail et sélectionnez-le dans VSCode (en bas à gauche).

---

## 📂 Organisation du projet

L’arborescence générale du projet suit cette structure :

```
matrice-od/
│
├── Data/            # Données brutes et traitées (non versionnées)
├── Notebooks/       # Notebooks Jupyter d'analyse et de traitement
├── src/             # Scripts Python du cœur du projet
├── temp_/           # Fichiers temporaires
├── requirements.txt
├── README.md
├── WORKFLOW.md
├── CONTRIBUTING.md
└── .gitignore
```

---

## 🚀 Installation complète

### 1️⃣ Cloner le projet
```bash
git clone https://github.com/ton-utilisateur/index-marchabilite-ge.git
cd index-marchabilite-ge
```

### 2️⃣ Configurer l’environnement de travail
Suivez les instructions ci-dessus pour créer et activer le venv, puis installez les dépendances :

```bash
pip install -r requirements.txt
```

---

## 🔧 Utilisation

- **Lancer le script principal** :
  ```bash
  python main.py
  ```
- **Exécuter les tests** :
  ```bash
  pytest tests/
  ```

- **Travailler avec des notebooks** :
  Ouvrir les fichiers `.ipynb` dans VSCode via l’extension Jupyter.

---

## 📜 Licence
Ce projet est sous licence [MIT](LICENSE).

---

## 📬 Contact
Pour toute question, contactez-nous via GitHub Issues.
