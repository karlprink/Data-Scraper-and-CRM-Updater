import requests


class AriregisterClient:
    
    def __init__(self):
        pass

    def get_csv(self, url, headers, stream=False):
        response = requests.get(url, headers=headers, stream=stream)
        response.raise_for_status()
        return response