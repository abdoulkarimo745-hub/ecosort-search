# ♻️ SmartBin (EcoSort-Search)

> Pipeline de collecte libre, Deep Learning multiclasse et déploiement Docker pour aider les citoyens à trier leurs déchets.

## 🎯 Objectif

SmartBin est une application web containerisée d'aide au tri sélectif. L'utilisateur saisit le nom d'un produit de consommation courante, l'application interroge en direct **Jumia** (scraping) pour proposer une liste de résultats correspondants, puis un modèle de **Deep Learning** analyse le produit sélectionné et affiche la consigne de tri exacte (couleur de la poubelle correspondante).

## 🏷️ Catégories de tri

| Catégorie | Couleur | Produits cibles | Matières (dataset) |
| :--- | :--- | :--- | :--- |
| Poubelle jaune | 🟡 Jaune | Bouteilles plastique, canettes, boîtes de conserve, briques de lait, flacons, cartons de colis | `plastic`, `metal`, `cardboard` |
| Poubelle verte | 🟢 Vert | Bouteilles en verre, pots de confiture, bocaux | `glass` |
| Poubelle bleue | 🔵 Bleu | Prospectus, journaux, magazines, cahiers, livres, enveloppes | `paper` |
| Bac électronique (D3E) | ⚫ Gris | Smartphones, écouteurs, chargeurs, mixeurs, montres | à cartographier par classe/mots-clés |
| Poubelle marron/noire | 🟤 Marron | Déchets résiduels non recyclables : restes alimentaires, sachets plastiques souples, produits d'hygiène | `trash` |

## 🏗️ Architecture

```
SmartBin/
├── app/                # Application web (Streamlit) — orchestration UI + scraping + inférence
│   └── main.py
├── model/               # Entraînement du modèle de classification
│   └── train.py
├── scraper/             # Scraping du moteur de recherche Jumia
│   └── jumia_scraper.py
├── requirements.txt     # Dépendances Python
├── Dockerfile           # Image de l'application
├── docker-compose.yml   # (optionnel) Orchestration du conteneur
└── .gitignore
```

### Jalon 1 — Entraînement de l'IA
- Dataset de référence : [Garbage Classification](https://www.kaggle.com/code/muhammedabdulazeem/garbage-classification) (Kaggle) — classes `glass`, `paper`, `cardboard`, `plastic`, `metal`, `trash`.
- Modèle : CNN custom ou Transfer Learning (`MobileNetV2`, `ResNet`...) via Keras/TensorFlow.
- Livrable : script d'entraînement reproductible (`model/train.py`) + modèle sauvegardé (ex. `modele_eco_sort.h5`).

### Jalon 2 — Collecte libre & déploiement
- `scraper/jumia_scraper.py` interroge le moteur de recherche Jumia à partir du mot-clé saisi par l'utilisateur et retourne 3 à 5 résultats pertinents.
- `app/main.py` (Streamlit) charge le modèle entraîné, exécute le scraping à la volée, et affiche la consigne de tri en coloriant l'écran selon la poubelle correspondante.
- L'ensemble est packagé dans un `Dockerfile`.

## 🚀 Installation & lancement

### En local
```bash
python -m venv .venv
source .venv/bin/activate  # Windows : .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app/main.py
```

### Avec Docker
```bash
docker build -t smartbin .
docker run -p 8501:8501 smartbin
```

Ou avec Docker Compose :
```bash
docker-compose up -d --build
```

L'application est ensuite accessible sur [http://localhost:8501](http://localhost:8501).

## 🧠 Entraînement du modèle

```bash
python model/train.py
```

Le script attend le dataset Kaggle téléchargé localement (non versionné, voir `.gitignore`) et produit le fichier de modèle utilisé par l'application.

## 👥 Équipe & workflow Git

- Projet réalisé en équipe de 3 étudiants, avec un historique de commits réparti sur trois branches distinctes.
- **Aucun push direct sur `main`** : tout ajout de code passe par une Pull Request revue et validée par un autre membre de l'équipe.
- Le dataset Kaggle et les environnements virtuels (`.venv/`, `__pycache__/`) ne sont jamais versionnés (voir `.gitignore`).

## 📅 Échéance

Date limite : **25/07/2026 23:59:59**. Des points bonus sont accordés en cas de rendu anticipé (0,5 pt/jour, plafonné à 5 pts) ; une pénalité de 2 pts/jour s'applique en cas de retard.
