import requests


class CompanyWebsiteClient:

    def __init__(self):
        pass

    def get_company_website(self, website_url, headers, timeout=10):
        response = requests.get(website_url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response