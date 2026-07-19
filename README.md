# ♻️ EcoSort-Search

> Pipeline de collecte libre, Deep Learning multiclasse et déploiement Docker pour aider les citoyens à trier leurs déchets.

## 🎯 Objectif

EcoSort-Search est une application web containerisée d'aide au tri sélectif. L'utilisateur saisit le nom d'un produit de consommation courante, l'application interroge en direct **Jumia** (scraping) pour proposer une liste de résultats correspondants, puis un modèle de **Deep Learning** analyse l'image du produit sélectionné et affiche la consigne de tri exacte (couleur de la poubelle correspondante).

## 🏷️ Catégories de tri

| Catégorie | Couleur | Produits cibles | Matières (dataset) |
| :--- | :--- | :--- | :--- |
| Poubelle jaune | 🟡 Jaune | Bouteilles plastique, canettes, boîtes de conserve, briques de lait, flacons, cartons de colis | `plastic`, `metal`, `cardboard` |
| Poubelle verte | 🟢 Vert | Bouteilles en verre, pots de confiture, bocaux | `glass` |
| Poubelle bleue | 🔵 Bleu | Prospectus, journaux, magazines, cahiers, livres, enveloppes | `paper` |
| Bac électronique (D3E) | ⚫ Gris | Smartphones, écouteurs, chargeurs, mixeurs, montres | pas de classe dédiée dans le dataset → détecté par mots-clés dans le nom du produit (voir `model/predict.py`) |
| Poubelle marron/noire | 🟤 Marron | Déchets résiduels non recyclables : restes alimentaires, sachets plastiques souples, produits d'hygiène | `trash` |

## 🏗️ Architecture

```
EcoSort-Search/
├── app/                     # Application web (Flask) — orchestration UI + scraping + inférence
│   ├── main.py
│   ├── static/
│   │   ├── style.css        # Feuille de style commune (typographie, composants)
│   │   ├── js/throw.js      # Animation de "jet" du produit vers la bonne poubelle
│   │   └── images/          # Photos des 5 poubelles + photo de fond du hero
│   └── templates/
│       ├── base.html        # Squelette commun (nav, variables de page/catégorie)
│       ├── search.html      # Page principale : hero + recherche + rangée des 5 poubelles + résultats
│       ├── result.html      # Page classify : fond = image de la poubelle + écran coloré
│       └── guide.html       # Guide de tri (5 poubelles alignées avec descriptions)
├── model/
│   ├── train.py             # Entraînement du modèle (Jalon 1)
│   ├── predict.py           # Inférence utilisée par l'appli (Jalon 1 → Jalon 2)
│   ├── modele_eco_sort.h5   # Généré par train.py (non versionné, voir .gitignore)
│   └── class_names.json     # Généré par train.py (ordre des classes du modèle)
├── scraper/
│   └── jumia_scraper.py     # Scraping du moteur de recherche Jumia (Jalon 2)
├── tests/
│   ├── test_app.py          # Tests des routes Flask (scraper/modèle mockés)
│   ├── test_scraper.py       # Tests unitaires du parsing HTML Jumia
│   └── test_predict.py       # Tests de l'heuristique de secours (sans modèle entraîné)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .gitignore
```

**Important :** l'application est en **Flask** (pas Streamlit) : `app/main.py` sert des templates Jinja via `render_template`. Parcours utilisateur : la page principale (`/`) affiche le hero, la barre de recherche et la rangée des 5 poubelles ; une recherche (`POST /search`) affiche les résultats **sur la même page**, sous les poubelles. Au clic sur « Voir la poubelle », le JavaScript (`static/js/throw.js`) appelle `POST /api/classify` pour connaître la poubelle cible, anime le **jet du produit vers cette poubelle**, puis soumet le formulaire vers `POST /classify` (en réutilisant la catégorie déjà calculée, pour ne pas classifier deux fois) : l'écran prend alors la couleur de la poubelle, avec l'image de la poubelle en fond. Sans JavaScript, le formulaire fonctionne quand même (POST classique, classification côté serveur).

### Jalon 1 — Entraînement de l'IA ✅
- Dataset de référence : [Garbage Classification](https://www.kaggle.com/code/muhammedabdulazeem/garbage-classification) (Kaggle) — classes `glass`, `paper`, `cardboard`, `plastic`, `metal`, `trash`.
- Modèle : Transfer Learning `MobileNetV2` (Keras/TensorFlow), tête de classification entraînée sur les 6 classes du dataset.
- Livrables : `model/train.py` (entraînement reproductible) + `model/predict.py` (inférence) + modèle sauvegardé `model/modele_eco_sort.h5` une fois `train.py` lancé.

### Jalon 2 — Collecte libre & déploiement ✅
- `scraper/jumia_scraper.py` interroge `https://www.jumia.ci/catalog/?q=<mot-clé>` et retourne jusqu'à 5 résultats (nom, prix, image, lien produit). En cas d'échec réseau ou de changement de structure HTML, il retourne une liste vide plutôt que de planter — voir le docstring du fichier pour adapter les sélecteurs CSS si besoin.
- `model/predict.py` expose `classify(product)` : mots-clés électroniques → catégorie D3E directement ; sinon l'image du produit (fournie par le scraper) est classée par le modèle CNN entraîné (Jalon 1), puis convertie en couleur de poubelle. **Tant que `model/train.py` n'a pas été lancé sur le vrai dataset, `classify()` retombe automatiquement sur une heuristique par mots-clés** afin que l'application reste démontrable sans modèle entraîné.
- `app/main.py` (Flask) orchestre scraping + classification et affiche la consigne de tri en coloriant l'écran selon la poubelle correspondante.
- L'ensemble est packagé dans un `Dockerfile`.

## 🚀 Installation & lancement

### En local
```bash
python -m venv .venv
source .venv/bin/activate  # Windows : .venv\Scripts\activate
pip install -r requirements.txt
python app/main.py
```
L'application est accessible sur [http://localhost:8501](http://localhost:8501).

> `tensorflow` (dans `requirements.txt`) est un paquet volumineux (500 Mo+). Il n'est nécessaire que pour `model/train.py` et pour l'inférence CNN réelle dans `model/predict.py` ; sans lui (ou sans modèle entraîné), l'application fonctionne quand même grâce au repli par mots-clés.

### Avec Docker
```bash
docker build -t ecosort .
docker run -p 8501:8501 ecosort
```

Ou avec Docker Compose :
```bash
docker-compose up -d --build
```

## 🧠 Entraînement du modèle

1. Télécharge le dataset Kaggle [Garbage Classification](https://www.kaggle.com/code/muhammedabdulazeem/garbage-classification) et dézippe-le (il doit contenir un sous-dossier par classe : `cardboard/`, `glass/`, `metal/`, `paper/`, `plastic/`, `trash/`).
2. Lance :
   ```bash
   python model/train.py --data-dir chemin/vers/dataset --epochs 15
   ```
3. Le script produit `model/modele_eco_sort.h5` et `model/class_names.json`. `app/main.py` les utilise automatiquement au prochain lancement — aucune autre configuration nécessaire.

Options utiles : `--epochs`, `--batch-size`, `--img-size`, `--fine-tune` (dégèle les dernières couches de MobileNetV2 pour un second passage d'entraînement). Voir `python model/train.py --help`.

## ✅ Tester le projet en local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt      # ou seulement flask/requests/beautifulsoup4/pillow/numpy si tensorflow est trop long à installer
python -m unittest discover -s tests -v
```

Les 3 fichiers de tests couvrent :
- **`test_app.py`** : les 5 routes Flask (`/`, `/guide`, `/search`, `/classify`, `/api/classify`) — le scraper et le modèle sont mockés, donc ces tests passent sans connexion internet ni modèle entraîné. Vérifie aussi que `/classify` réutilise la catégorie pré-calculée par `/api/classify` sans relancer l'inférence.
- **`test_scraper.py`** : le parsing HTML du scraper Jumia sur un fragment HTML factice (pas de vrai appel réseau).
- **`test_predict.py`** : l'heuristique de secours de `classify()` (mots-clés → catégorie), utilisée tant que le modèle n'est pas entraîné.

Pour tester manuellement dans le navigateur :
```bash
python app/main.py
```
puis ouvre [http://localhost:8501](http://localhost:8501), fais une recherche, clique sur un produit pour voir la consigne de tri.

**Remarque sur le scraper en conditions réelles :** la structure HTML de Jumia peut évoluer. Si une recherche ne renvoie aucun résultat alors que ta connexion fonctionne, ouvre `https://www.jumia.ci/catalog/?q=<mot>` dans un navigateur, inspecte une carte produit (clic droit > Inspecter) et compare avec les sélecteurs CSS en tête de `scraper/jumia_scraper.py`.

## 👥 Équipe & workflow Git

- Projet réalisé en équipe de 3 étudiants, avec un historique de commits réparti sur trois branches distinctes.
- **Aucun push direct sur `main`** : tout ajout de code passe par une Pull Request revue et validée par un autre membre de l'équipe.
- Le dataset Kaggle et les environnements virtuels (`.venv/`, `__pycache__/`) ne sont jamais versionnés (voir `.gitignore`).

## 📅 Échéance

Date limite : **25/07/2026 23:59:59**. Des points bonus sont accordés en cas de rendu anticipé (0,5 pt/jour, plafonné à 5 pts) ; une pénalité de 2 pts/jour s'applique en cas de retard.
