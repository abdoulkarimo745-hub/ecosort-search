import os
import sys

from flask import Flask, jsonify, render_template, request

# Garantit que la racine du projet est sur sys.path, quel que soit le
# répertoire depuis lequel ce fichier est lancé (python app/main.py, flask run...).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Intégration scraper/modèle -------------------------------------------
# Le scraper (scraper/jumia_scraper.py) doit exposer :
#   search_products(query: str) -> list[dict]  avec au moins les clés "name" et "price"
# Le modèle (model/predict.py) doit exposer :
#   classify_with_confidence(product: dict) -> tuple[str, float]
#   renvoyant (clé parmi CATEGORIES, confiance de la prédiction ∈ [0, 1])
# Tant que ces fonctions ne sont pas prêtes, on retombe sur des mocks locaux.
try:
    from scraper.jumia_scraper import search_products_all as search_products
except ImportError:
    try:
        from scraper.jumia_scraper import search_products  # ancienne version mono-pays
    except ImportError:
        search_products = None

try:
    from model.predict import classify_with_confidence
except ImportError:
    classify_with_confidence = None

CATEGORIES = {
    "jaune": {
        "label": "Poubelle JAUNE",
        "short": "Jaune",
        "emoji": "🟡",
        "image": "jaune.png",
        "color": "#FFD400",
        "text_color": "#1a1a1a",
        "desc": "Emballages légers : plastique, métal, canettes, cartons.",
        "examples": ["Bouteilles plastique", "Canettes", "Boîtes de conserve", "Briques alimentaires"],
    },
    "verte": {
        "label": "Poubelle VERTE",
        "short": "Verte",
        "emoji": "🟢",
        "image": "verte.png",
        "color": "#2E7D32",
        "text_color": "#ffffff",
        "desc": "Emballages en verre : bouteilles, pots, bocaux.",
        "examples": ["Bouteilles en verre", "Pots et bocaux", "Flacons en verre"],
    },
    "bleue": {
        "label": "Poubelle BLEUE",
        "short": "Bleue",
        "emoji": "🔵",
        "image": "bleue.png",
        "color": "#1565C0",
        "text_color": "#ffffff",
        "desc": "Papiers graphiques : journaux, magazines, cahiers, enveloppes.",
        "examples": ["Journaux et magazines", "Cartons pliés", "Cahiers, enveloppes"],
    },
    "d3e": {
        "label": "Bac ÉLECTRONIQUE (D3E)",
        "short": "D3E",
        "emoji": "⚙️",
        "image": "d3e.png",
        "color": "#616161",
        "text_color": "#ffffff",
        "desc": "Appareils électriques/électroniques : téléphones, chargeurs, écouteurs.",
        "examples": ["Téléphones", "Chargeurs", "Écouteurs", "Petits appareils électroniques"],
    },
    "marron": {
        "label": "Poubelle MARRON / NOIRE",
        "short": "Marron",
        "emoji": "🟤",
        "image": "marron.png",
        "color": "#4E342E",
        "text_color": "#ffffff",
        "desc": "Déchets résiduels non recyclables.",
        "examples": ["Déchets alimentaires souillés", "Résidus non recyclables", "Emballages sales"],
    },
}

# Chaque route indique sa page ("search", "results", "result", "guide") via
# la variable `page` : base.html s'en sert pour poser une classe CSS sur le
# <body> (motif de fond différent par page, voir style.css). On n'utilise
# plus de photos de fond externes (Unsplash) : ça évite une dépendance
# réseau fragile pour un simple habillage visuel, et l'appli reste
# entièrement fonctionnelle hors ligne (utile le jour d'une démo/correction).


def mock_search_products(query):
    return [
        {"name": f"{query} - Bouteille plastique 1L", "price": "1 500 FCFA", "image": "https://images.unsplash.com/photo-1600103414137-2b5b8a6ec4c8?auto=format&fit=crop&w=900&q=80"},
        {"name": f"{query} - Emballage carton", "price": "2 500 FCFA", "image": "https://images.unsplash.com/photo-1512820790803-83ca734da794?auto=format&fit=crop&w=900&q=80"},
        {"name": f"{query} - Version en verre", "price": "3 000 FCFA", "image": "https://images.unsplash.com/photo-1600103414137-2b5b8a6ec4c8?auto=format&fit=crop&w=900&q=80"},
        {"name": f"{query} Électronique Pro", "price": "15 000 FCFA", "image": "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=900&q=80"},
        {"name": f"{query} - Sachet souple", "price": "800 FCFA", "image": "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?auto=format&fit=crop&w=900&q=80"},
    ]


def get_product_image(product_name, product=None):
    name = (product_name or "").lower()
    if product and product.get("image"):
        return product.get("image")
    if any(word in name for word in ["verre", "bocal", "bouteille", "bottle"]):
        return "https://images.unsplash.com/photo-1600103414137-2b5b8a6ec4c8?auto=format&fit=crop&w=900&q=80"
    if any(word in name for word in ["papier", "carton", "journal", "cahier", "livre", "enveloppe"]):
        return "https://images.unsplash.com/photo-1512820790803-83ca734da794?auto=format&fit=crop&w=900&q=80"
    if any(word in name for word in ["électronique", "electronique", "telephone", "téléphone", "chargeur", "écouteur", "ecouteur", "batterie"]):
        return "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=900&q=80"
    if any(word in name for word in ["plastique", "sachet", "metal", "métal", "canette", "conserve"]):
        return "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?auto=format&fit=crop&w=900&q=80"
    return "https://images.unsplash.com/photo-1490645935967-10de6ba17061?auto=format&fit=crop&w=900&q=80"


def mock_classify(product):
    """Mock de classify_with_confidence() : renvoie (catégorie, confiance)."""
    name = product["name"].lower()
    if any(word in name for word in ["verre", "bocal", "pot", "confiture"]):
        return "verte", 0.96
    if any(word in name for word in ["papier", "journal", "cahier", "livre", "enveloppe"]):
        return "bleue", 0.94
    if any(word in name for word in ["électronique", "electronique", "telephone", "téléphone", "chargeur", "écouteur", "ecouteur", "batterie"]):
        return "d3e", 0.98
    if any(word in name for word in ["plastique", "métal", "metal", "carton", "canette", "conserve"]):
        return "jaune", 0.93
    return "marron", 0.72


search_fn = search_products or mock_search_products
classify_fn = classify_with_confidence or mock_classify
using_mocks = search_products is None or classify_with_confidence is None

app = Flask(__name__)

# --- Préchauffage du modèle CNN -------------------------------------------
# Le modèle TensorFlow n'était chargé qu'à la PREMIÈRE classification :
# cette première requête subissait alors le "démarrage à froid" (chargement
# du .h5 + compilation de la première inférence, plusieurs secondes sur
# CPU), donnant l'impression que l'application ne répond pas. On précharge
# donc le modèle dès le démarrage du serveur, dans un thread pour ne pas
# retarder l'affichage de la page d'accueil.
def _warm_up_model_async():
    try:
        from model.predict import warm_up
    except ImportError:
        return  # mode mocks : rien à préchauffer
    import threading

    threading.Thread(target=warm_up, daemon=True).start()


_warm_up_model_async()


@app.route("/", methods=["GET"])
def index():
    # Page 1/3 : uniquement la barre de recherche.
    return render_template(
        "search.html",
        using_mocks=using_mocks,
        active="search",
        page="search",
        categories=CATEGORIES,
        query=None,
        results=None,
    )


@app.route("/guide", methods=["GET"])
def guide():
    return render_template(
        "guide.html",
        categories=CATEGORIES,
        active="guide",
        page="guide",
    )


@app.route("/about", methods=["GET"])
def about():
    # Page « À propos » : objectif du site, fonctionnalités clés, et
    # présentation des auteurs (élèves ingénieurs statisticiens) et de
    # leur enseignant.
    authors = [
        {"name": "OUATTARA Abdoul Karim", "classe": "ISE2A"},
        {"name": "ESSIENNE Ezanne Frédéric", "classe": "ISE2A"},
        {"name": "TOTON Nicodème Mahugnon", "classe": "ISE2B"},
    ]
    return render_template(
        "about.html",
        authors=authors,
        teacher="M. KANGA Boris Parfait",
        active="about",
        page="about",
    )


@app.route("/search", methods=["POST"])
def search():
    # Recherche et résultats vivent sur la MÊME page (search.html) : la
    # rangée des 5 poubelles reste visible au-dessus des résultats, ce qui
    # permet l'animation de "jet" du produit vers la bonne poubelle (voir
    # app/static/js/throw.js).
    query = request.form.get("query", "").strip()
    results = search_fn(query) if query else []
    enriched_results = []
    for product in results:
        product_copy = dict(product)
        product_copy["image"] = get_product_image(product_copy.get("name", ""), product_copy)
        enriched_results.append(product_copy)
    return render_template(
        "search.html",
        using_mocks=using_mocks,
        active="search",
        page="results",
        categories=CATEGORIES,
        query=query,
        results=enriched_results,
    )


@app.route("/api/classify", methods=["POST"])
def api_classify():
    # Classification en JSON, appelée par le JavaScript AVANT de quitter la
    # page : il faut connaître la poubelle cible pour animer le jet du
    # produit vers la bonne poubelle de la rangée. Le résultat est ensuite
    # retransmis au POST /classify (champs cachés category/confidence) pour
    # ne pas classifier deux fois le même produit.
    data = request.get_json(silent=True) or {}
    product = {
        "name": data.get("name", ""),
        "price": data.get("price", ""),
        "image": data.get("image", ""),
    }
    category_key, confidence = classify_fn(product)
    return jsonify({"category": category_key, "confidence": confidence})


@app.route("/classify", methods=["POST"])
def classify_selected():
    # Page finale : l'écran prend la couleur de la poubelle du produit.
    product = {
        "name": request.form.get("name", ""),
        "price": request.form.get("price", ""),
        "image": request.form.get("image", ""),
        "url": request.form.get("url", ""),
        "country": request.form.get("country", ""),
        "flag": request.form.get("flag", ""),
    }
    query = request.form.get("query", "")

    # Si le JavaScript de la page de recherche a déjà classifié le produit
    # (via /api/classify, pour animer le jet vers la bonne poubelle), la
    # catégorie et la confiance arrivent en champs cachés : on les réutilise
    # pour ne pas re-télécharger l'image ni relancer le modèle. Toute valeur
    # absente ou invalide déclenche une classification normale.
    category_key = request.form.get("category", "")
    confidence = None
    if category_key in CATEGORIES:
        try:
            confidence = float(request.form.get("confidence", ""))
        except ValueError:
            confidence = None
    if category_key not in CATEGORIES or confidence is None:
        category_key, confidence = classify_fn(product)

    category = CATEGORIES[category_key]
    if not product["image"]:
        product["image"] = get_product_image(product.get("name", ""), product)
    return render_template(
        "result.html",
        using_mocks=using_mocks,
        active="search",
        page="result",
        query=query,
        selected=product,
        category=category,
        confidence=confidence,
    )


if __name__ == "__main__":
    # debug=True uniquement en local (FLASK_DEBUG=1) : le débogueur Werkzeug
    # permet d'exécuter du code arbitraire et ne doit jamais tourner dans le
    # conteneur Docker. Par défaut (Docker, prod) : debug désactivé.
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode, host="0.0.0.0", port=8501)
