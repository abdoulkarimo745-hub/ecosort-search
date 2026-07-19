import unittest
from unittest.mock import patch, Mock

import requests
from bs4 import BeautifulSoup

from scraper.jumia_scraper import search_products, _parse_product_card

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
        product = _parse_product_card(self.cards[0])
        self.assertEqual(product["name"], "Bouteille plastique 1L")
        self.assertEqual(product["price"], "1,500.00 FCFA")
        self.assertEqual(product["image"], "https://cdn.jumia.ci/img/bouteille1.jpg")
        self.assertEqual(product["url"], "https://www.jumia.ci/generic-bouteille-plastique-1l-19699793.html")

    def test_keeps_already_absolute_url(self):
        product = _parse_product_card(self.cards[1])
        self.assertEqual(product["url"], "https://www.jumia.ci/generic-bocal-en-verre-31364600.html")

    def test_card_without_link_is_ignored(self):
        self.assertIsNone(_parse_product_card(self.cards[2]))


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


if __name__ == "__main__":
    unittest.main()
