"""Scraper Jumia multi-pays — EcoSort-Search / Jalon 2.

Interroge les moteurs de recherche des sites Jumia de TOUS les pays où la
plateforme opère (Côte d'Ivoire, Nigeria, Kenya, Égypte, Maroc, Ghana,
Sénégal, Ouganda, Algérie) à partir d'un mot-clé, et retourne une liste de
produits, chacun annoté du pays d'origine (nom + drapeau) affiché dans
l'interface.

Utilisé par app/main.py :

    from scraper.jumia_scraper import search_products_all
    results = search_products_all("bouteille")
    # -> [{"name": ..., "price": ..., "image": ..., "url": ...,
    #      "country": "Côte d'Ivoire", "flag": "🇨🇮"}, ...]

Les sites sont interrogés EN PARALLÈLE (ThreadPoolExecutor) : le temps
total de la recherche est celui du site le plus lent, pas la somme des 9.
Un site qui échoue (réseau, blocage, structure HTML modifiée) est
simplement ignoré : la recherche continue avec les autres pays.

`search_products(query, limit, country)` reste disponible pour interroger
un seul pays (compatibilité + tests unitaires).

NB pédagogique : la structure HTML de Jumia est partagée entre les pays
(mêmes sélecteurs CSS). Si un site ne renvoie plus de résultats alors que
la requête réseau réussit (code 200), ouvre la page de recherche du site
dans un navigateur, inspecte une carte produit (clic droit > Inspecter) et
adapte les sélecteurs CSS ci-dessous.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Les sites Jumia actifs, dans l'ordre d'affichage souhaité (la Côte
# d'Ivoire d'abord : c'est le marché local du projet).
JUMIA_SITES = {
    "ci": {"base": "https://www.jumia.ci", "country": "Côte d'Ivoire", "flag": "🇨🇮"},
    "sn": {"base": "https://www.jumia.sn", "country": "Sénégal", "flag": "🇸🇳"},
    "ng": {"base": "https://www.jumia.com.ng", "country": "Nigeria", "flag": "🇳🇬"},
    "gh": {"base": "https://www.jumia.com.gh", "country": "Ghana", "flag": "🇬🇭"},
    "ke": {"base": "https://www.jumia.co.ke", "country": "Kenya", "flag": "🇰🇪"},
    "ug": {"base": "https://www.jumia.ug", "country": "Ouganda", "flag": "🇺🇬"},
    "ma": {"base": "https://www.jumia.ma", "country": "Maroc", "flag": "🇲🇦"},
    "dz": {"base": "https://www.jumia.dz", "country": "Algérie", "flag": "🇩🇿"},
    "eg": {"base": "https://www.jumia.com.eg", "country": "Égypte", "flag": "🇪🇬"},
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}
TIMEOUT = 8  # secondes, par site

# Sélecteurs CSS d'une carte produit Jumia (structure partagée entre pays) :
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


def _parse_product_card(card, base_url):
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
    url = urljoin(base_url, href)

    if not name:
        return None

    return {"name": name, "price": price, "image": image, "url": url}


def search_products(query, limit=5, country="ci"):
    """Recherche `query` sur le site Jumia d'UN pays donné.

    Retourne une liste de dicts {name, price, image, url, country, flag}.
    Retourne [] si la requête échoue ou si aucun produit n'est trouvé.
    """
    query = (query or "").strip()
    site = JUMIA_SITES.get(country)
    if not query or site is None:
        return []

    try:
        response = requests.get(
            f"{site['base']}/catalog/",
            params={"q": query},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Jumia %s : échec de la requête réseau (%s)", country, exc)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.select(CARD_SELECTOR)

    results = []
    for card in cards:
        product = _parse_product_card(card, site["base"])
        if product:
            product["country"] = site["country"]
            product["flag"] = site["flag"]
            results.append(product)
        if len(results) >= limit:
            break

    if not results:
        logger.info(
            "Jumia %s : aucun résultat pour %r — la structure HTML a "
            "peut-être changé, voir le docstring de ce module.",
            country,
            query,
        )

    return results


def search_products_all(query, per_country=2, max_results=10):
    """Recherche `query` sur TOUS les sites Jumia, en parallèle.

    Retourne jusqu'à `max_results` produits (au plus `per_country` par
    pays), ordonnés par pays selon l'ordre de JUMIA_SITES (Côte d'Ivoire
    en tête). Les sites en échec sont simplement ignorés.
    """
    query = (query or "").strip()
    if not query:
        return []

    per_country_results = {}
    with ThreadPoolExecutor(max_workers=len(JUMIA_SITES)) as pool:
        futures = {
            pool.submit(search_products, query, per_country, code): code
            for code in JUMIA_SITES
        }
        for future in as_completed(futures):
            code = futures[future]
            try:
                per_country_results[code] = future.result()
            except Exception:  # garde-fou : un pays ne doit jamais tout casser
                logger.exception("Jumia %s : erreur inattendue", code)
                per_country_results[code] = []

    results = []
    for code in JUMIA_SITES:  # ordre d'affichage stable, CI d'abord
        results.extend(per_country_results.get(code, []))
        if len(results) >= max_results:
            break

    return results[:max_results]


if __name__ == "__main__":
    # Petit outil manuel : `python scraper/jumia_scraper.py bouteille`
    import sys

    logging.basicConfig(level=logging.INFO)
    mot_cle = sys.argv[1] if len(sys.argv) > 1 else "bouteille"
    for produit in search_products_all(mot_cle):
        print(produit)
