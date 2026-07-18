"""Scraper Jumia (Côte d'Ivoire) — SmartBin / Jalon 2.

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