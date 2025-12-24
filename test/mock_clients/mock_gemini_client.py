from unittest.mock import MagicMock

EXPECTED_PROMPT_STAFF = ["""
    Your task is to act as a data analyst. Analyze the following website text and extract
    contact information for specific roles only.

    Return the data ONLY as a JSON array. Each object in the array must be in
    the following format:
    {{
      "name": "Name Here",
      "role": "Role Title Here",
      "email": "email address OR null",
      "phone": "phone number OR null"
    }}

    KEY ROLES TO FIND (by priority):
    I am interested ONLY in these roles. Please include Estonian equivalents.

    1. STRATEGIC LEADERSHIP:
       - 'CEO', 'Tegevjuht'
       - 'COO', 'Chief Operating Officer'
       - 'CIO', 'Chief Information Officer'
       - 'CTO', 'Chief Technology Officer'
       - 'Managing Director'
       - 'Founder'

    2. DEVELOPMENT / TECHNOLOGY:
       - 'Arendusjuht', 'Head of Development'
       - 'IT-juht', 'IT Manager', 'Head of IT'
       - 'Innovatsioonijuht', 'Head of Innovation'

    3. PROJECT MANAGEMENT:
       - 'Projektijuht', 'Project Manager'

    4. PERSONNEL / MARKETING:
       - 'HR Manager', 'Personalijuht'
       - 'Head of Marketing', 'Turundusjuht'
       - 'Head of Sales', 'Müügijuht'

    5. GENERAL CONTACT:
       - 'General Contact'

    RULES:
    1. Find the name, role, email, AND phone number.
    2. If email or phone is not found, set the value to `null` (not "MISSING" or similar).
    3. Ignore all other roles that are not in the list above (e.g., "Project Manager", "Specialist" are too general).
    4. If you find a general contact (like "info@..." or a general phone number), add it as a separate object where the `role` is "General Contact".
    5. If you do not find ANY relevant contacts, return ONLY an empty array `[]`.
    6. Do not add anything else to your response (like "Here is the JSON:", "```json") besides the JSON itself.


    TEXT CONTENT:
    ---
    """,
    """
    ---
    Finish analysis and return ONLY JSON.
    """
                         ]

EXPECTED_PROMPT_PAGE = ["""
    The following is a list of links found on the website """,
    """
    .
    Which of these URLs most likely leads to a page containing
    company staff, team, or contact information (e.g., "Contact", "Team", "About Us")?

    List of links (in the format "link text: URL"):
    ---
    """,
    """
    ---

    Please respond with only the single, most suitable URL. If url includes "team", "tiim", "meeskond", "staff", "team members", "tootajad", "töötajad" then this is most likely the best URL. Url containing "meist" is probably not the best URL. If none are suitable, return: "NONE"
    """
                        ]

class MockGeminiClient():
    def __init__(self, model):
        self.model = model
        self.generate_content_called = MagicMock()

#    def generate_content(self, prompt):
        #TODO

