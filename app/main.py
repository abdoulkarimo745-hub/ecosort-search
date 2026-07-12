import os
import sys

from flask import Flask, render_template, request

# Garantit que la racine du projet est sur sys.path, quel que soit le
# répertoire depuis lequel ce fichier est lancé (python app/main.py, flask run...).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Intégration scraper/modèle -------------------------------------------
# Le scraper (scraper/jumia_scraper.py) doit exposer :
#   search_products(query: str) -> list[dict]  avec au moins les clés "name" et "price"
# Le modèle (model/predict.py, à créer) doit exposer :
#   classify(product: dict) -> str  renvoyant une clé parmi CATEGORIES
# Tant que ces fonctions ne sont pas prêtes, on retombe sur des mocks locaux.
try:
    from scraper.jumia_scraper import search_products
except ImportError:
    search_products = None

try:
    from model.predict import classify
except ImportError:
    classify = None

CATEGORIES = {
    "jaune": {
        "label": "Poubelle JAUNE",
        "emoji": "🟡",
        "color": "#FFD400",
        "text_color": "#1a1a1a",
        "desc": "Emballages légers : plastique, métal, canettes, cartons.",
    },
    "verte": {
        "label": "Poubelle VERTE",
        "emoji": "🟢",
        "color": "#2E7D32",
        "text_color": "#ffffff",
        "desc": "Emballages en verre : bouteilles, pots, bocaux.",
    },
    "bleue": {
        "label": "Poubelle BLEUE",
        "emoji": "🔵",
        "color": "#1565C0",
        "text_color": "#ffffff",
        "desc": "Papiers graphiques : journaux, magazines, cahiers, enveloppes.",
    },
    "d3e": {
        "label": "Bac ÉLECTRONIQUE (D3E)",
        "emoji": "⚙️",
        "color": "#616161",
        "text_color": "#ffffff",
        "desc": "Appareils électriques/électroniques : téléphones, chargeurs, écouteurs.",
    },
    "marron": {
        "label": "Poubelle MARRON / NOIRE",
        "emoji": "🟤",
        "color": "#4E342E",
        "text_color": "#ffffff",
        "desc": "Déchets résiduels non recyclables.",
    },
}


def mock_search_products(query):
    return [
        {"name": f"{query} - Bouteille plastique 1L", "price": "1 500 FCFA"},
        {"name": f"{query} - Emballage carton", "price": "2 500 FCFA"},
        {"name": f"{query} - Version en verre", "price": "3 000 FCFA"},
        {"name": f"{query} Électronique Pro", "price": "15 000 FCFA"},
        {"name": f"{query} - Sachet souple", "price": "800 FCFA"},
    ]


def mock_classify(product):
    name = product["name"].lower()
    if any(word in name for word in ["verre", "bocal", "pot", "confiture"]):
        return "verte"
    if any(word in name for word in ["papier", "journal", "cahier", "livre", "enveloppe"]):
        return "bleue"
    if any(word in name for word in ["électronique", "electronique", "telephone", "téléphone", "chargeur", "écouteur", "ecouteur", "batterie"]):
        return "d3e"
    if any(word in name for word in ["plastique", "métal", "metal", "carton", "canette", "conserve"]):
        return "jaune"
    return "marron"


search_fn = search_products or mock_search_products
classify_fn = classify or mock_classify
using_mocks = search_products is None or classify is None

app = Flask(__name__)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", using_mocks=using_mocks)


@app.route("/search", methods=["POST"])
def search():
    query = request.form.get("query", "").strip()
    results = search_fn(query) if query else []
    return render_template("index.html", using_mocks=using_mocks, query=query, results=results)


@app.route("/classify", methods=["POST"])
def classify_selected():
    product = {
        "name": request.form.get("name", ""),
        "price": request.form.get("price", ""),
    }
    query = request.form.get("query", "")
    category = CATEGORIES[classify_fn(product)]
    return render_template(
        "index.html",
        using_mocks=using_mocks,
        query=query,
        selected=product,
        category=category,
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8501)
