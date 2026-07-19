"""Module d'inférence EcoSort-Search — Jalon 1 / Jalon 2.

Expose :

    classify_with_confidence(product: dict) -> tuple[str, float]

qui renvoie (clé de catégorie, confiance ∈ [0, 1]), la clé étant l'une des
catégories définies dans app/main.py ("jaune", "verte", "bleue", "d3e",
"marron"). classify(product) est conservée pour compatibilité et renvoie
uniquement la clé.

Fonctionnement :
  1. Si le nom du produit contient un mot-clé électronique (téléphone,
     chargeur, écouteur, ...), on renvoie directement "d3e" : le dataset
     Kaggle "Garbage Classification" utilisé pour l'entraînement (Jalon 1)
     ne contient pas de classe électronique, voir README.md.
  2. Sinon, si un modèle entraîné existe (model/modele_eco_sort.h5, produit
     par `python model/train.py`), on télécharge l'image du produit
     (fournie par le scraper Jumia) et on la fait classer par le CNN parmi
     les 6 matières du dataset (cardboard, glass, metal, paper, plastic,
     trash), puis on convertit vers la couleur de poubelle correspondante.
  3. Si le modèle n'a pas encore été entraîné (fichier absent) ou si l'image
     n'est pas exploitable (URL manquante, téléchargement impossible), on
     retombe sur une heuristique par mots-clés afin que l'application reste
     utilisable même avant l'entraînement du modèle.

Ce module est importé par app/main.py :

    from model.predict import classify
"""
import json
import logging
import os

logger = logging.getLogger(__name__)

MODEL_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(MODEL_DIR, "modele_eco_sort.h5")
CLASS_NAMES_PATH = os.path.join(MODEL_DIR, "class_names.json")
IMG_SIZE = 160  # doit correspondre à --img-size utilisé pour l'entraînement

# Mapping "matière" (classes du dataset Kaggle) -> "catégorie EcoSort-Search"
# (couleur de poubelle), voir le tableau dans README.md.
#
# Deux datasets Kaggle "Garbage Classification" sont supportés :
#   - version 6 classes  (asdasdasasdas/garbage-classification) :
#       cardboard, glass, metal, paper, plastic, trash
#   - version 12 classes (mostafaabla/garbage-classification) :
#       + battery, biological, brown/green/white-glass, clothes, shoes
# Le modèle utilise les classes trouvées dans le dataset d'entraînement
# (sauvegardées dans class_names.json par train.py) ; ce dict couvre les deux.
# Avantage de la version 12 classes : la classe `battery` permet de router
# vers le bac D3E par une VRAIE prédiction du modèle ("classe dédiée" du
# sujet), en plus de la détection par mots-clés sur le nom du produit.
MATERIAL_TO_CATEGORY = {
    # --- communs aux deux datasets ---
    "cardboard": "jaune",
    "metal": "jaune",
    "plastic": "jaune",
    "glass": "verte",
    "paper": "bleue",
    "trash": "marron",
    # --- version 12 classes uniquement ---
    "battery": "d3e",
    "biological": "marron",
    "brown-glass": "verte",
    "green-glass": "verte",
    "white-glass": "verte",
    "clothes": "marron",   # textiles : pas d'emballage recyclable -> résiduel
    "shoes": "marron",
}

D3E_KEYWORDS = [
    "électronique", "electronique", "telephone", "téléphone", "smartphone",
    "chargeur", "écouteur", "ecouteur", "casque", "batterie",
    "ordinateur", "tablette", "console", "clavier", "souris",
]

_model = None
_class_names = None
_model_load_attempted = False


def _load_model():
    """Charge (une seule fois) le modèle entraîné, si le fichier existe."""
    global _model, _class_names, _model_load_attempted

    if _model_load_attempted:
        return _model
    _model_load_attempted = True

    if not os.path.exists(MODEL_PATH):
        logger.info(
            "Aucun modèle entraîné trouvé (%s). Lance `python model/train.py "
            "--data-dir <dataset>` pour l'entraîner. En attendant, la "
            "classification par mots-clés est utilisée.",
            MODEL_PATH,
        )
        return None

    try:
        import tensorflow as tf  # import tardif : tensorflow n'est requis qu'ici

        _model = tf.keras.models.load_model(MODEL_PATH)
    except Exception:
        logger.exception("Échec du chargement du modèle %s", MODEL_PATH)
        return None

    if os.path.exists(CLASS_NAMES_PATH):
        with open(CLASS_NAMES_PATH, encoding="utf-8") as f:
            _class_names = json.load(f)
    else:
        # Ordre alphabétique par défaut (celui produit par
        # tf.keras.utils.image_dataset_from_directory).
        _class_names = ["cardboard", "glass", "metal", "paper", "plastic", "trash"]

    return _model


def _keyword_fallback(product):
    """Heuristique de secours (utilisée sans modèle entraîné ou sans image)."""
    name = (product.get("name") or "").lower()
    if any(word in name for word in ["verre", "bocal", "pot", "confiture"]):
        return "verte"
    if any(word in name for word in ["papier", "journal", "cahier", "livre", "enveloppe"]):
        return "bleue"
    if any(word in name for word in ["plastique", "métal", "metal", "carton", "canette", "conserve"]):
        return "jaune"
    return "marron"


def _download_image(url):
    import requests
    from PIL import Image
    import io

    response = requests.get(url, timeout=8)
    response.raise_for_status()
    return Image.open(io.BytesIO(response.content)).convert("RGB")


def _predict_material(image):
    """Fait passer une image PIL dans le modèle et renvoie (matière, confiance).

    Le modèle produit par model/train.py contient déjà une couche Rescaling
    en première position : on lui donne donc directement des pixels bruts
    [0, 255], sans normalisation manuelle ici. La confiance est la
    probabilité softmax de la classe retenue (argmax).
    """
    import numpy as np

    resized = image.resize((IMG_SIZE, IMG_SIZE))
    batch = np.expand_dims(np.array(resized), axis=0).astype("float32")
    predictions = _model.predict(batch, verbose=0)
    index = int(np.argmax(predictions[0]))
    confidence = float(predictions[0][index])
    return _class_names[index], confidence


def classify_with_confidence(product):
    """Renvoie (clé de catégorie EcoSort-Search, confiance ∈ [0, 1]) pour `product`.

    `product` doit contenir au moins la clé "name". La clé "image" (URL),
    si présente, est utilisée pour la classification par le modèle CNN.
    Une décision par règle (mot-clé électronique ou repli heuristique) n'est
    pas une probabilité de modèle : sa confiance vaut 1.0 par convention.
    """
    name = (product.get("name") or "").lower()

    if any(word in name for word in D3E_KEYWORDS):
        return "d3e", 1.0

    model = _load_model()
    image_url = product.get("image")

    if model is None or not image_url:
        return _keyword_fallback(product), 1.0

    try:
        image = _download_image(image_url)
        material, confidence = _predict_material(image)
        return MATERIAL_TO_CATEGORY.get(material, "marron"), confidence
    except Exception:
        logger.exception(
            "Échec de la classification par image pour %r, repli sur les mots-clés",
            product.get("name"),
        )
        return _keyword_fallback(product), 1.0


def classify(product):
    """Renvoie uniquement la clé de catégorie EcoSort-Search (sans la confiance).

    Conservé pour compatibilité : voir classify_with_confidence() pour la
    version utilisée par l'application, qui expose aussi la confiance de la
    prédiction.
    """
    return classify_with_confidence(product)[0]


def warm_up():
    """Précharge le modèle et exécute une inférence à blanc.

    À appeler au démarrage du serveur (idéalement dans un thread, voir
    app/main.py) : sans cela, la PREMIÈRE classification d'un utilisateur
    subit le "démarrage à froid" de TensorFlow (chargement du .h5 +
    compilation de la première inférence), soit plusieurs secondes sur CPU —
    ce qui peut donner l'impression que l'application ne répond pas.
    """
    model = _load_model()
    if model is None:
        return False
    try:
        import numpy as np

        dummy = np.zeros((1, IMG_SIZE, IMG_SIZE, 3), dtype="float32")
        model.predict(dummy, verbose=0)
        logger.info("Modèle préchauffé : la première classification sera rapide.")
        return True
    except Exception:
        logger.exception("Échec du préchauffage du modèle")
        return False
