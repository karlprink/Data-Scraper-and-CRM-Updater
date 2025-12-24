class GeminiClient:
    """Class for communicating with Gemini API"""
    def __init__(self, model):
        self.model = model

    def generate_content(self, prompt):
        response = self.model.generate_content(prompt)
        return response