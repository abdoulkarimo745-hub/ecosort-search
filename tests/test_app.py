import unittest
from unittest.mock import patch

from app.main import app


class EcoSortAppTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_home_page_renders(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Guide de tri", response.data)

    def test_guide_page_renders(self):
        response = self.client.get("/guide")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Guide de tri", response.data)

    @patch("app.main.search_fn")
    def test_search_results_render_as_product_cards(self, mock_search_fn):
        # On mocke le scraper Jumia : les tests ne doivent jamais dépendre
        # d'un vrai accès réseau (flaky en CI, et impossible hors ligne).
        mock_search_fn.return_value = [
            {
                "name": "Bouteille plastique 1L",
                "price": "1 500 FCFA",
                "image": "https://images.unsplash.com/photo-test.jpg",
                "url": "https://www.jumia.ci/exemple.html",
            },
        ]
        response = self.client.post(
            "/search",
            data={"query": "bouteille"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"product-card", response.data)
        self.assertIn(b"Voir", response.data)
        mock_search_fn.assert_called_once_with("bouteille")

    @patch("app.main.classify_fn")
    def test_classify_result_renders_fullscreen_overlay(self, mock_classify_fn):
        # On mocke la classification : les tests ne doivent pas dépendre d'un
        # modèle CNN entraîné (model/modele_eco_sort.h5 n'existe pas encore
        # tant que model/train.py n'a pas été lancé sur le vrai dataset).
        mock_classify_fn.return_value = ("verte", 0.87)
        response = self.client.post(
            "/classify",
            data={
                "name": "Produit test",
                "price": "1 000 FCFA",
                "image": "https://images.unsplash.com/photo-test.jpg",
                "query": "test",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"result-overlay", response.data)
        self.assertIn("Poubelle VERTE".encode("utf-8"), response.data)
        self.assertIn(b"87%", response.data)
        mock_classify_fn.assert_called_once()

    def test_about_page_lists_authors_and_teacher(self):
        response = self.client.get("/about")
        self.assertEqual(response.status_code, 200)
        for expected in ["OUATTARA Abdoul Karim", "ESSIENNE Ezanne Frédéric",
                         "TOTON Nicodème Mahugnon", "KANGA Boris Parfait"]:
            self.assertIn(expected.encode("utf-8"), response.data)

    @patch("app.main.classify_fn")
    def test_api_classify_returns_category_as_json(self, mock_classify_fn):
        # /api/classify est appelée par js/throw.js AVANT l'animation de jet
        # pour connaître la poubelle cible.
        mock_classify_fn.return_value = ("d3e", 0.95)
        response = self.client.post(
            "/api/classify",
            json={"name": "Smartphone", "price": "80 000 FCFA", "image": "https://x/img.jpg"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["category"], "d3e")
        self.assertAlmostEqual(payload["confidence"], 0.95)
        mock_classify_fn.assert_called_once()

    @patch("app.main.classify_fn")
    def test_classify_reuses_precomputed_category_without_reclassifying(self, mock_classify_fn):
        # Quand le JS transmet la catégorie déjà calculée par /api/classify,
        # /classify ne doit PAS relancer la classification (pas de double
        # téléchargement d'image ni de double inférence).
        response = self.client.post(
            "/classify",
            data={
                "name": "Bouteille en verre",
                "price": "1 000 FCFA",
                "image": "https://x/img.jpg",
                "query": "bouteille",
                "category": "verte",
                "confidence": "0.91",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Poubelle VERTE".encode("utf-8"), response.data)
        self.assertIn(b"91%", response.data)
        mock_classify_fn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
