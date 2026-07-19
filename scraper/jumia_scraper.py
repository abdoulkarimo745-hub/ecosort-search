"""Scraper Jumia (Côte d'Ivoire) — EcoSort-Search / Jalon 2.

Interroge le moteur de recherche de Jumia (https://www.jumia.ci) à partir
d'un mot-clé saisi par l'utilisateur et retourne une liste de produits.

Utilisé par app/main.py :

    from scraper.jumia_scraper import search_products
    results = search_products("bouteille")
    # -> [{"name": ..., "price": ..., "image": ..., "url": ...}, ...]

Important : si la requête échoue (pas de réseau, page bloquée, structure
HTML modifiée par Jumia), `search_products` renvoie une liste VIDE plutôt que
de lever une exception, afin que l'application Flask puisse retomber sur les
données de démonstration (voir `using_mocks` dans app/main.py). Un message
est simplement écrit dans les logs pour te permettre de diagnostiquer.

NB pédagogique : la structure HTML de Jumia peut évoluer. Si `search_products`
renvoie toujours une liste vide alors que la requête réseau réussit (code 200),
ouvre https://www.jumia.ci/catalog/?q=<mot> dans un navigateur, fais clic
droit > Inspecter sur une carte produit, et adapte les sélecteurs CSS dans
`_parse_product_card` ci-dessous (variable `card`).
"""
import logging
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.jumia.ci"
SEARCH_URL = f"{BASE_URL}/catalog/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
}
TIMEOUT = 8  # secondes

# Sélecteurs CSS utilisés par la plateforme Jumia pour une carte produit dans
# une page de résultats de recherche. Ce sont les sélecteurs "historiques" et
# les plus courants sur les sites Jumia (structure partagée entre les pays) :
#   <article class="prd _fb col c-prd">
#     <a class="core" href="...">
#       <div class="img-c"><img data-src="..." class="img" /></div>
#       <h3 class="name">Nom du produit</h3>
#       <div class="prc">12 345 FCFA</div>
#     </a>
#   </article>
CARD_SELECTOR = "article.prd"
LINK_SELECTOR = "a.core"
NAME_SELECTOR = "h3.name"
PRICE_SELECTOR = "div.prc"


def _parse_product_card(card):
    """Extrait un dict {name, price, image, url} depuis une carte produit."""
    link = card.select_one(LINK_SELECTOR)
    if link is None:
        return None

    name_el = card.select_one(NAME_SELECTOR)
    price_el = card.select_one(PRICE_SELECTOR)
    img_el = card.select_one("img")

    name = name_el.get_text(strip=True) if name_el else (link.get("title") or "").strip()
    price = price_el.get_text(strip=True) if price_el else ""

    image = ""
    if img_el is not None:
        # Jumia charge les images en lazy-loading : l'URL réelle est dans
        # data-src (l'attribut src pointe souvent vers un placeholder).
        image = img_el.get("data-src") or img_el.get("src") or ""

    href = link.get("href", "")
    url = urljoin(BASE_URL, href)

    if not name:
        return None

    return {"name": name, "price": price, "image": image, "url": url}


def search_products(query, limit=5):
    """Recherche `query` sur Jumia CI et retourne jusqu'à `limit` produits.

    Retourne une liste de dicts avec les clés "name", "price", "image", "url".
    Retourne [] si la requête échoue ou si aucun produit n'est trouvé.
    """
    query = (query or "").strip()
    if not query:
        return []

    try:
        response = requests.get(
            SEARCH_URL,
            params={"q": query},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Jumia scraper : échec de la requête réseau (%s)", exc)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.select(CARD_SELECTOR)

    results = []
    for card in cards:
        product = _parse_product_card(card)
        if product:
            results.append(product)
        if len(results) >= limit:
            break

    if not results:
        logger.info(
            "Jumia scraper : aucun résultat pour %r — la structure HTML a "
            "peut-être changé, voir le docstring de ce module.",
            query,
        )

    return results


if __name__ == "__main__":
    # Petit outil manuel : `python scraper/jumia_scraper.py bouteille`
    import sys

    logging.basicConfig(level=logging.INFO)
    mot_cle = sys.argv[1] if len(sys.argv) > 1 else "bouteille"
    for produit in search_products(mot_cle):
        print(produit)
