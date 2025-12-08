import requests


class GoogleClient:
    """Class for communicating with Google API"""

    def __init__(self, key, cx):
        self.key = key
        self.cx = cx

    def get_search_results(
        self, query, timeout=6, result_number=10, gl="ee", lr="lang_et|lang_en"
    ):
        """Returns data as json file."""
        params = {
            "key": self.key,
            "cx": self.cx,
            "q": query,
            "num": result_number,
            "gl": gl,
            "lr": lr,
        }
        r = requests.get(
            "https://www.googleapis.com/customsearch/v1", params=params, timeout=timeout
        )
        r.raise_for_status()
        return r.json()
