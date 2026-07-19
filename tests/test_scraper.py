import unittest
from unittest.mock import patch, Mock

import requests
from bs4 import BeautifulSoup

from scraper.jumia_scraper import JUMIA_SITES, search_products, search_products_all, _parse_product_card

BASE_CI = "https://www.jumia.ci"

# Fragment HTML imitant la structure d'une page de résultats Jumia
# (une "carte produit" par <article class="prd">). Utilisé pour tester le
# parsing SANS dépendre d'un vrai accès réseau à jumia.ci.
FAKE_SEARCH_HTML = """
<html><body>
<article class="prd _fb col c-prd">
  <a class="core" href="/generic-bouteille-plastique-1l-19699793.html" title="Bouteille plastique 1L">
    <div class="img-c"><img data-src="https://cdn.jumia.ci/img/bouteille1.jpg" class="img" /></div>
    <div class="info">
      <h3 class="name">Bouteille plastique 1L</h3>
      <div class="prc">1,500.00 FCFA</div>
    </div>
  </a>
</article>
<article class="prd _fb col c-prd">
  <a class="core" href="https://www.jumia.ci/generic-bocal-en-verre-31364600.html" title="Bocal en verre">
    <div class="img-c"><img data-src="https://cdn.jumia.ci/img/bocal.jpg" class="img" /></div>
    <div class="info">
      <h3 class="name">Bocal en verre 500ml</h3>
      <div class="prc">2,900.00 FCFA</div>
    </div>
  </a>
</article>
<article class="prd _fb col c-prd">
  <div class="info"><h3 class="name">Carte cassée sans lien</h3></div>
</article>
</body></html>
"""


class ParseProductCardTest(unittest.TestCase):
    def setUp(self):
        soup = BeautifulSoup(FAKE_SEARCH_HTML, "html.parser")
        self.cards = soup.select("article.prd")

    def test_parses_name_price_image_and_absolute_url(self):
        product = _parse_product_card(self.cards[0], BASE_CI)
        self.assertEqual(product["name"], "Bouteille plastique 1L")
        self.assertEqual(product["price"], "1,500.00 FCFA")
        self.assertEqual(product["image"], "https://cdn.jumia.ci/img/bouteille1.jpg")
        self.assertEqual(product["url"], "https://www.jumia.ci/generic-bouteille-plastique-1l-19699793.html")

    def test_keeps_already_absolute_url(self):
        product = _parse_product_card(self.cards[1], BASE_CI)
        self.assertEqual(product["url"], "https://www.jumia.ci/generic-bocal-en-verre-31364600.html")

    def test_card_without_link_is_ignored(self):
        self.assertIsNone(_parse_product_card(self.cards[2], BASE_CI))


class SearchProductsTest(unittest.TestCase):
    @patch("scraper.jumia_scraper.requests.get")
    def test_builds_query_and_parses_results(self, mock_get):
        fake_response = Mock()
        fake_response.text = FAKE_SEARCH_HTML
        fake_response.raise_for_status = Mock()
        mock_get.return_value = fake_response

        results = search_products("bouteille", limit=5)

        self.assertEqual(len(results), 2)  # la carte cassée est filtrée
        self.assertEqual(results[0]["name"], "Bouteille plastique 1L")
        self.assertEqual(results[0]["country"], "Côte d'Ivoire")
        self.assertEqual(results[0]["flag"], "🇨🇮")
        mock_get.assert_called_once()
        self.assertEqual(mock_get.call_args.kwargs["params"], {"q": "bouteille"})

    @patch("scraper.jumia_scraper.requests.get")
    def test_respects_limit(self, mock_get):
        fake_response = Mock()
        fake_response.text = FAKE_SEARCH_HTML
        fake_response.raise_for_status = Mock()
        mock_get.return_value = fake_response

        results = search_products("bouteille", limit=1)
        self.assertEqual(len(results), 1)

    @patch("scraper.jumia_scraper.requests.get", side_effect=requests.exceptions.ConnectionError("boom"))
    def test_network_failure_returns_empty_list(self, mock_get):
        self.assertEqual(search_products("bouteille"), [])

    def test_empty_query_returns_empty_list_without_request(self):
        self.assertEqual(search_products("   "), [])


class SearchProductsAllTest(unittest.TestCase):
    @patch("scraper.jumia_scraper.search_products")
    def test_aggregates_countries_in_stable_order(self, mock_search):
        # Seuls la CI et le Nigeria renvoient des résultats ; les autres
        # pays échouent (liste vide) et sont simplement ignorés.
        def fake(query, limit=5, country="ci"):
            if country in ("ci", "ng"):
                site = JUMIA_SITES[country]
                return [
                    {"name": f"P-{country}-{i}", "price": "1", "image": "", "url": "",
                     "country": site["country"], "flag": site["flag"]}
                    for i in range(limit)
                ]
            return []

        mock_search.side_effect = fake
        results = search_products_all("bouteille", per_country=2, max_results=10)

        self.assertEqual(len(results), 4)
        # La Côte d'Ivoire (marché local) est toujours affichée en premier.
        self.assertEqual(results[0]["country"], "Côte d'Ivoire")
        self.assertEqual(results[2]["country"], "Nigeria")

    @patch("scraper.jumia_scraper.search_products")
    def test_respects_max_results(self, mock_search):
        def fake(query, limit=5, country="ci"):
            site = JUMIA_SITES[country]
            return [{"name": f"P-{country}", "price": "1", "image": "", "url": "",
                     "country": site["country"], "flag": site["flag"]}] * limit

        mock_search.side_effect = fake
        results = search_products_all("bouteille", per_country=2, max_results=5)
        self.assertEqual(len(results), 5)

    def test_empty_query_returns_empty_list(self):
        self.assertEqual(search_products_all("  "), [])


if __name__ == "__main__":
    unittest.main()
