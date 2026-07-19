# ♻️ EcoSort-Search

> Pipeline de collecte libre, Deep Learning multiclasse et déploiement Docker pour aider les citoyens à trier leurs déchets.

## 🎯 Objectif

EcoSort-Search est une application web containerisée d'aide au tri sélectif. L'utilisateur saisit le nom d'un produit de consommation courante ; l'application interroge en direct **Jumia** (scraping) pour proposer une liste de résultats correspondants ; une fois un produit sélectionné, un modèle de **Deep Learning** l'analyse et affiche la consigne de tri exacte en colorant l'écran aux couleurs de la poubelle correspondante.

## 🏷️ Catégories de tri

| Catégorie | Couleur | Produits cibles | Matières (dataset) |
| :--- | :--- | :--- | :--- |
| Poubelle jaune | 🟡 Jaune | Bouteilles plastique, canettes, boîtes de conserve, briques de lait, flacons, cartons de colis | `plastic`, `metal`, `cardboard` |
| Poubelle verte | 🟢 Vert | Bouteilles en verre, pots de confiture, bocaux | `glass`, `brown-glass`, `green-glass`, `white-glass` |
| Poubelle bleue | 🔵 Bleu | Prospectus, journaux, magazines, cahiers, livres, enveloppes | `paper` |
| Bac électronique (D3E) | ⚫ Gris | Smartphones, écouteurs, chargeurs, mixeurs, montres | classe dédiée `battery` du dataset **+** détection par mots-clés dans le nom du produit (`model/predict.py`) — double sécurité |
| Poubelle marron/noire | 🟤 Marron | Déchets résiduels non recyclables : restes alimentaires, sachets plastiques souples, produits d'hygiène | `trash`, `biological`, `clothes`, `shoes` |

## 🏗️ Architecture

```
EcoSort-Search/
├── app/
│   ├── main.py               # Routes Flask : recherche, résultats, classify, api/classify
│   ├── static/
│   │   ├── style.css         # Feuille de style (typographie, glassmorphism, composants)
│   │   ├── js/
│   │   │   ├── throw.js      # Animation + son du "jet" du produit vers la bonne poubelle
│   │   │   └── carousel.js   # Défilement des images du hero (pages recherche & guide)
│   │   └── images/
│   │       ├── bins/         # Photos détourées des 5 poubelles (jaune, verte, bleue, d3e, marron)
│   │       ├── carousel/     # Photos du hero en carousel (1 par catégorie de tri)
│   │       └── bins-background.jpg  # Fond flouté (effet "verre") des pages recherche/guide
│   └── templates/
│       ├── base.html         # Squelette commun (nav, variables de page/catégorie)
│       ├── _carousel.html    # Partial Jinja du carousel (inclus dans search.html et guide.html)
│       ├── search.html       # Page principale : hero + recherche + rangée des 5 poubelles + résultats
│       ├── result.html       # Page classify : écran coloré à la couleur de la poubelle
│       └── guide.html        # Guide de tri (5 poubelles alignées avec descriptions)
├── model/
│   ├── train.py               # Entraînement du modèle (Jalon 1)
│   ├── predict.py              # Inférence + préchauffage du modèle (Jalon 1 → Jalon 2)
│   ├── modele_eco_sort.h5      # Généré par train.py (versionné : 26 Mo, sous la limite GitHub)
│   └── class_names.json        # Généré par train.py (ordre des classes du modèle)
├── scraper/
│   └── jumia_scraper.py       # Scraping du moteur de recherche Jumia (Jalon 2)
├── tests/
│   ├── test_app.py             # Tests des routes Flask (scraper/modèle mockés)
│   ├── test_scraper.py         # Tests unitaires du parsing HTML Jumia
│   └── test_predict.py         # Tests de l'heuristique de secours (sans modèle entraîné)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
└── .gitignore
```

**Stack technique :** application **Flask** (templates Jinja via `render_template`, pas Streamlit) ; scraping avec **Requests + BeautifulSoup** ; modèle **Transfer Learning MobileNetV2** (Keras/TensorFlow).

**Parcours utilisateur :** la page principale (`/`) affiche un hero en carousel (photos illustrant chaque catégorie de tri), la barre de recherche, et la rangée des 5 poubelles. Une recherche (`POST /search`) affiche les résultats **sur la même page**, sous les poubelles, avec pour chaque produit un lien **« Voir sur Jumia »** vers la vraie fiche produit (permet de vérifier que le produit existe réellement). Au clic sur « Voir la poubelle », le JavaScript (`static/js/throw.js`) appelle `POST /api/classify` pour connaître la poubelle cible, anime le **jet du produit vers cette poubelle** (trajectoire en arc + son), puis soumet le formulaire vers `POST /classify` (en réutilisant la catégorie déjà calculée, pour ne pas classifier deux fois) : l'écran prend alors la couleur de la poubelle. Sans JavaScript, le formulaire fonctionne quand même (POST classique, classification côté serveur).

**Performance :** le modèle CNN est **préchargé en mémoire au démarrage du serveur** (`model/predict.py::warm_up()`, lancé dans un thread par `app/main.py`), pour que la première classification d'un utilisateur soit aussi rapide que les suivantes (pas de "démarrage à froid" de TensorFlow perceptible).

### Jalon 1 — Entraînement de l'IA ✅
- Dataset utilisé : [Garbage Classification](https://www.kaggle.com/datasets/mostafaabla/garbage-classification) (Kaggle, 12 classes, ~15 500 images) — une extension du dataset de référence du sujet (6 classes) qui ajoute notamment `battery`, permettant de router le bac **D3E par une vraie classe dédiée du modèle** plutôt que par mots-clés seuls (les deux options étaient acceptées par le sujet).
- Modèle : Transfer Learning `MobileNetV2` (Keras/TensorFlow), tête de classification entraînée sur les 12 classes, avec fine-tuning des dernières couches (`--fine-tune`). Précision finale sur le jeu de validation : voir la sortie de `model/train.py` (~92 % après 2 époques sans fine-tuning, davantage attendu avec l'entraînement complet).
- Livrables : `model/train.py` (entraînement reproductible, cache disque pour limiter l'usage RAM) + `model/predict.py` (inférence + mapping matière → couleur de poubelle) + modèle sauvegardé `model/modele_eco_sort.h5`.

### Jalon 2 — Collecte libre & déploiement ✅
- `scraper/jumia_scraper.py` interroge `https://www.jumia.ci/catalog/?q=<mot-clé>` (BeautifulSoup + Requests) et retourne jusqu'à 5 résultats (nom, prix, image, **lien vers la vraie fiche produit**). En cas d'échec réseau ou de changement de structure HTML, il retourne une liste vide plutôt que de planter — voir le docstring du fichier pour adapter les sélecteurs CSS si besoin.
- `model/predict.py` expose `classify_with_confidence(product)` : mots-clés électroniques → catégorie D3E directement ; sinon l'image du produit (fournie par le scraper) est classée par le modèle CNN, puis convertie en couleur de poubelle avec un score de confiance. Si le modèle n'est pas encore entraîné ou si l'image est inexploitable, repli automatique sur une heuristique par mots-clés.
- `app/main.py` (Flask) orchestre scraping + classification et affiche la consigne de tri en coloriant l'écran selon la poubelle correspondante.
- L'ensemble est packagé dans un `Dockerfile` (image testée avec succès via `docker build` + `docker run`).

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

L'image embarque le modèle entraîné (`model/modele_eco_sort.h5`) : l'inférence CNN réelle fonctionne dès le premier `docker run`, sans étape supplémentaire.

## 🧠 Entraînement du modèle (reproductibilité)

1. Télécharge le dataset Kaggle [Garbage Classification (12 classes)](https://www.kaggle.com/datasets/mostafaabla/garbage-classification) et dézippe-le (il doit contenir un sous-dossier par classe : `battery/`, `biological/`, `brown-glass/`, `cardboard/`, `clothes/`, `green-glass/`, `metal/`, `paper/`, `plastic/`, `shoes/`, `trash/`, `white-glass/`).
2. Lance :
   ```bash
   python model/train.py --data-dir chemin/vers/dataset --epochs 12 --fine-tune
   ```
3. Le script produit `model/modele_eco_sort.h5` et `model/class_names.json`. `app/main.py` les utilise automatiquement au prochain lancement — aucune autre configuration nécessaire.

Options utiles : `--epochs`, `--batch-size` (défaut 16, pour limiter l'usage mémoire), `--img-size`, `--fine-tune` (dégèle les dernières couches de MobileNetV2 pour un second passage d'entraînement). Voir `python model/train.py --help`.

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
- **`test_predict.py`** : l'heuristique de secours de `classify()` (mots-clés → catégorie), utilisée tant que le modèle n'est pas entraîné ou sans image.

Pour tester manuellement dans le navigateur :
```bash
python app/main.py
```
puis ouvre [http://localhost:8501](http://localhost:8501), fais une recherche, clique sur un produit pour voir le jet animé et la consigne de tri.

**Remarque sur le scraper en conditions réelles :** la structure HTML de Jumia peut évoluer. Si une recherche ne renvoie aucun résultat alors que la connexion fonctionne, ouvre `https://www.jumia.ci/catalog/?q=<mot>` dans un navigateur, inspecte une carte produit (clic droit > Inspecter) et compare avec les sélecteurs CSS en tête de `scraper/jumia_scraper.py`.

## 👥 Équipe & workflow Git

- Projet réalisé en équipe de 3 étudiants, avec un historique de commits réparti sur trois branches distinctes.
- **Aucun push direct sur `main`** : tout ajout de code passe par une Pull Request revue et validée par un autre membre de l'équipe.
- Le dataset Kaggle et les environnements virtuels (`.venv/`, `__pycache__/`) ne sont jamais versionnés (voir `.gitignore` et `.dockerignore`).

