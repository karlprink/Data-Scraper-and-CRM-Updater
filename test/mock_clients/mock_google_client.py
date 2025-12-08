from unittest.mock import MagicMock

import requests


class MockGoogleClient:
    def __init__(self, key, cx):
        self.key = key
        self.cx = cx
        self.get_search_results_called = MagicMock()

    def get_search_results(
        self, query, timeout=6, result_number=10, gl="ee", lr="lang_ee|lang_en"
    ):
        params = {
            "key": self.key,
            "cx": self.cx,
            "q": query,
            "num": result_number,
            "gl": gl,
            "lr": lr,
        }
        if (
            params["q"] == "OÜ Ideelabor official website"
        ):  # for mimicking a proper response
            return {"items": [{"link": "https://ideelabor.ee"}, {"link": "teatmik.ee"}]}
        if (
            params["q"] == "2S2B Social Media OÜ official website"
        ):  # for mimicking google API failures
            raise requests.HTTPError()
        return None
