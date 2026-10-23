import unittest
import analyzer


class TestCEI(unittest.TestCase):
    def test_rating_boundaries(self):
        self.assertEqual(analyzer.classify_cei(85), "GOOD")
        self.assertEqual(analyzer.classify_cei(84.99), "MODERATE")
        self.assertEqual(analyzer.classify_cei(60), "MODERATE")
        self.assertEqual(analyzer.classify_cei(59.99), "POOR")
        self.assertEqual(analyzer.classify_cei(None), "N/A")

    def test_core_balance(self):
        self.assertEqual(analyzer.calculate_core_balance([25, 25, 25, 25]), 100.0)
        self.assertEqual(analyzer.calculate_core_balance([92, 88, 15, 10]), 61.25)
        self.assertIsNone(analyzer.calculate_core_balance([]))

    def test_context_switch_requires_baseline(self):
        self.assertIsNone(analyzer.analyze_context_switches(1000, None))
        self.assertEqual(analyzer.analyze_context_switches(1500, 1000), 500)
        self.assertIsNone(analyzer.analyze_context_switches(10, 1000))

    def test_missing_components_are_provisional_and_normalized(self):
        score, mode, missing = analyzer.calculate_cei({
            "B": 80, "T": 70, "A": 90, "C": None, "H": None, "S": None
        })
        expected = (0.25 * 80 + 0.20 * 70 + 0.15 * 90) / 0.60
        self.assertAlmostEqual(score, round(expected, 2))
        self.assertEqual(mode, "provisional")
        self.assertEqual(missing, ["C", "H", "S"])

    def test_full_formula_keeps_original_weights(self):
        components = {"B": 100, "T": 80, "A": 60, "C": 40, "H": 20, "S": 0}
        score, mode, missing = analyzer.calculate_cei(components)
        self.assertEqual(score, 58.0)
        self.assertEqual(mode, "full")
        self.assertEqual(missing, [])

    def test_scalability_requires_comparison(self):
        self.assertIsNone(analyzer.calculate_scalability_score([]))
        self.assertIsNone(analyzer.calculate_scalability_score([{"Workers": 1, "Time": 2, "Speedup": 1}]))
        result = analyzer.calculate_scalability_score([
            {"Workers": 1, "Time": 8, "Speedup": 1.0},
            {"Workers": 2, "Time": 4.5, "Speedup": 1.78},
            {"Workers": 4, "Time": 2.5, "Speedup": 3.2},
        ])
        self.assertGreater(result, 0)
        self.assertLessEqual(result, 100)


if __name__ == "__main__":
    unittest.main()
