from unittest.mock import MagicMock

import requests


class MockAriregisterClient:

    def __init__(self):
        self.get_csv_called = MagicMock()
        with open("test/mock_cache/ariregister_data.zip", 'rb') as f:
            self.ariregister_data = f.read()

    def get_csv(self, url, headers, stream):
        if url == "fail_url":
            raise requests.HTTPError()

        response = MagicMock()
        response.raise_for_status = MagicMock()

        def iter_content(chunk_size):
            for i in range(0, len(self.ariregister_data), chunk_size):
                yield self.ariregister_data[i:i + chunk_size]
        response.iter_content = MagicMock(side_effect=iter_content)

        response.__enter__ = MagicMock(return_value=response)
        response.__exit__ = MagicMock(return_value=None)

        return response