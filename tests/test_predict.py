import unittest

from model.predict import classify

# Ces tests s'exécutent SANS modèle entraîné (model/modele_eco_sort.h5
# n'existe pas tant que `python model/train.py` n'a pas été lancé sur le
# vrai dataset Kaggle). classify() doit alors retomber sur l'heuristique par
# mots-clés et rester utilisable pour la démo/les tests.


class ClassifyKeywordFallbackTest(unittest.TestCase):
    def test_electronics_keyword_routes_to_d3e_even_without_model(self):
        self.assertEqual(classify({"name": "Chargeur téléphone rapide"}), "d3e")
        self.assertEqual(classify({"name": "Écouteurs sans fil"}), "d3e")

    def test_glass_keyword_maps_to_verte(self):
        self.assertEqual(classify({"name": "Bocal en verre 500ml"}), "verte")

    def test_paper_keyword_maps_to_bleue(self):
        self.assertEqual(classify({"name": "Cahier 200 pages"}), "bleue")

    def test_plastic_and_metal_keywords_map_to_jaune(self):
        self.assertEqual(classify({"name": "Bouteille plastique"}), "jaune")
        self.assertEqual(classify({"name": "Canette en métal"}), "jaune")

    def test_unknown_product_defaults_to_marron(self):
        self.assertEqual(classify({"name": "Objet non identifié xyz"}), "marron")

    def test_missing_image_falls_back_to_keywords(self):
        # Même si un modèle était chargé, sans URL d'image on ne peut pas
        # faire d'inférence CNN : on doit retomber sur les mots-clés.
        self.assertEqual(classify({"name": "Bocal en verre", "image": ""}), "verte")


if __name__ == "__main__":
    unittest.main()
