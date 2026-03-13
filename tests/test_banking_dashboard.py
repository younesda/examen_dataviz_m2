import unittest

import pandas as pd

from dashboards.banking_dashboard import _aggregate_by_company, _format_kpi_metric


class BankingDashboardAggregationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dataframe = pd.DataFrame(
            [
                {
                    "company": "Alpha Bank",
                    "year": 2021,
                    "bilan": 100.0,
                    "ressources": 80.0,
                    "fonds_propres": 10.0,
                    "produit_net_bancaire": 5.0,
                    "resultat_exploitation": 2.0,
                    "resultat_net": 1.0,
                    "effectif": 50.0,
                    "agence": 5.0,
                    "compte": 1000.0,
                },
                {
                    "company": "Alpha Bank",
                    "year": 2022,
                    "bilan": 120.0,
                    "ressources": 90.0,
                    "fonds_propres": 12.0,
                    "produit_net_bancaire": 6.0,
                    "resultat_exploitation": 3.0,
                    "resultat_net": 2.0,
                    "effectif": 55.0,
                    "agence": 6.0,
                    "compte": 1100.0,
                },
                {
                    "company": "Beta Bank",
                    "year": 2021,
                    "bilan": 200.0,
                    "ressources": 150.0,
                    "fonds_propres": 20.0,
                    "produit_net_bancaire": 8.0,
                    "resultat_exploitation": 4.0,
                    "resultat_net": 3.0,
                    "effectif": 70.0,
                    "agence": 7.0,
                    "compte": 1500.0,
                },
                {
                    "company": "Beta Bank",
                    "year": 2022,
                    "bilan": 210.0,
                    "ressources": 160.0,
                    "fonds_propres": 21.0,
                    "produit_net_bancaire": 9.0,
                    "resultat_exploitation": 5.0,
                    "resultat_net": 4.0,
                    "effectif": 72.0,
                    "agence": 8.0,
                    "compte": 1550.0,
                },
            ]
        )

    def test_company_aggregation_uses_latest_year_for_stock_metrics(self) -> None:
        aggregated = _aggregate_by_company(self.dataframe).set_index("company")

        self.assertEqual(aggregated.loc["Alpha Bank", "bilan"], 120.0)
        self.assertEqual(aggregated.loc["Alpha Bank", "fonds_propres"], 12.0)
        self.assertEqual(aggregated.loc["Alpha Bank", "compte"], 1100.0)
        self.assertEqual(aggregated.loc["Alpha Bank", "resultat_net"], 3.0)
        self.assertEqual(aggregated.loc["Alpha Bank", "produit_net_bancaire"], 11.0)

        self.assertEqual(aggregated.loc["Beta Bank", "bilan"], 210.0)
        self.assertEqual(aggregated.loc["Beta Bank", "fonds_propres"], 21.0)
        self.assertEqual(aggregated.loc["Beta Bank", "resultat_net"], 7.0)

    def test_kpi_formatter_can_switch_between_snapshot_and_cumulative_views(self) -> None:
        self.assertEqual(
            _format_kpi_metric(self.dataframe, "bilan", snapshot_latest_year=True),
            "330 FCFA",
        )
        self.assertEqual(
            _format_kpi_metric(self.dataframe, "resultat_net"),
            "10 FCFA",
        )


if __name__ == "__main__":
    unittest.main()
