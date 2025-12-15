import requests
import logging


class NotionClient:
    """Class for communicating with the Notion API."""

    def __init__(self, token: str, database_id: str, api_version: str = None):
        self.token = token
        self.database_id = database_id
        # Default to a recent API version if not provided
        self.api_version = api_version or "2022-06-28"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Notion-Version": self.api_version,
        }

    def get_page(self, page_id: str):
        """Returns data of a specific page."""
        url = f"https://api.notion.com/v1/pages/{page_id}"
        r = requests.get(url, headers=self.headers)
        r.raise_for_status()
        return r.json()

    def create_page(self, payload: dict):
        """Adds a new page (entry) to the database."""
        url = "https://api.notion.com/v1/pages"
        r = requests.post(url, headers=self.headers, json=payload)
        r.raise_for_status()
        return r.json()

    def update_page(self, page_id: str, properties: dict):
        """Updates an existing page (entry)."""
        url = f"https://api.notion.com/v1/pages/{page_id}"
        r = requests.patch(url, headers=self.headers, json={"properties": properties})
        r.raise_for_status()
        return r.json()

    def get_database(self):
        """Retrieves database schema/properties."""
        url = f"https://api.notion.com/v1/databases/{self.database_id}"
        r = requests.get(url, headers=self.headers)
        r.raise_for_status()
        return r.json()

    def _normalize_page_id(self, page_id: str) -> str:
        """Normalize a Notion page ID by removing hyphens for consistent comparison."""
        if not page_id:
            return ""
        # Remove hyphens and convert to lowercase for comparison
        return page_id.replace("-", "").lower()

    def query_by_regcode(self, regcode: str, exclude_page_id: str = None):
        """Searches for a page by registry code.

        Args:
            regcode: The registry code to search for
            exclude_page_id: Optional page ID to exclude from results (e.g., current page)

        Returns:
            The first matching page (excluding exclude_page_id if provided), or None
        """
        url = f"https://api.notion.com/v1/databases/{self.database_id}/query"

        payload = {
            "filter": {"property": "Registrikood", "number": {"equals": int(regcode)}}
        }

        all_results = []
        has_more = True
        next_cursor = None

        # Handle pagination to get all results
        while has_more:
            if next_cursor:
                payload["start_cursor"] = next_cursor

            r = requests.post(url, headers=self.headers, json=payload)
            r.raise_for_status()
            res = r.json()

            page_results = res.get("results", [])
            all_results.extend(page_results)

            has_more = res.get("has_more", False)
            next_cursor = res.get("next_cursor")

        if not all_results:
            return None

        # Normalize exclude_page_id for comparison
        exclude_id_normalized = None
        if exclude_page_id:
            exclude_id_normalized = self._normalize_page_id(exclude_page_id)
            logging.debug(f"Excluding page_id (normalized): {exclude_id_normalized}")

        # If exclude_page_id is provided, filter it out
        if exclude_id_normalized:
            logging.debug(
                f"Found {len(all_results)} pages with registrikood, checking for duplicates (excluding current page)"
            )
            for page in all_results:
                page_id = page.get("id", "")
                page_id_normalized = self._normalize_page_id(page_id)
                logging.debug(
                    f"Comparing: page_id={page_id}, normalized={page_id_normalized}, exclude={exclude_id_normalized}, match={page_id_normalized == exclude_id_normalized}"
                )
                if page_id_normalized != exclude_id_normalized:
                    logging.debug(
                        f"Found different page with same registrikood: {page_id}"
                    )
                    return page
            # All results were the excluded page, so no other page exists
            logging.debug(
                f"All {len(all_results)} results matched the excluded page_id, no duplicate found"
            )
            return None

        # Return first result if no exclusion needed
        return all_results[0]

    def query_database(self, filter_dict: dict):
        """Queries the database with a custom filter."""
        url = f"https://api.notion.com/v1/databases/{self.database_id}/query"
        payload = {"filter": filter_dict}
        r = requests.post(url, headers=self.headers, json=payload)
        r.raise_for_status()
        res = r.json()
        return res.get("results", [])

    def delete_page(self, page_id: str):
        """Archives (soft deletes) a page in Notion."""
        url = f"https://api.notion.com/v1/pages/{page_id}"
        payload = {"archived": True}
        r = requests.patch(url, headers=self.headers, json=payload)
        r.raise_for_status()
        return r.json()
