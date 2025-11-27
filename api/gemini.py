import os
import google.generativeai as genai
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse # Vajalik linkide parandamiseks
import json

from .clients.company_website_client import CompanyWebsiteClient

# Lae .env faili muutujad
load_dotenv()

# Konfigureerin kliendi
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))


try:
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
except Exception as e:
    print(f"Viga mudeli initsialiseerimisel: {e}")
    exit()

company_website_client = CompanyWebsiteClient()

def get_website_text(url):
    """Laeb veebilehe sisu alla ja puhastab selle tekstiks."""
    print(f"   ... Laen alla sisu aadressilt: {url}")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
        }
        response = company_website_client.get_company_website(url, headers)
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()
            
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        cleaned_text = '\n'.join(chunk for chunk in chunks if chunk)
        
        print("   ... Sisu edukalt alla laetud ja puhastatud.")
        return cleaned_text
        
    except requests.exceptions.RequestException as e:
        print(f"   ... Viga veebilehe allalaadimisel: {e}")
        return None

def find_contact_page_url(base_url):
    """
    Samm 1: Leiab pealehelt kõik lingid ja küsib Geminilt,
    milline neist kõige tõenäolisemalt sisaldab kontaktinfot.
    """
    print(f"Samm 1: Kontaktilehe otsimine pealehelt {base_url}...")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
        }
        response = company_website_client.get_company_website(base_url, headers)
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        links = []
        # Leiame kõik <a> (lingi) sildid
        for a_tag in soup.find_all('a', href=True):
            link_text = a_tag.get_text(strip=True).lower()
            link_href = a_tag['href']
            
            # Teisendame suhtelised lingid (nt /kontakt) täispikkadeks URL-ideks
            full_url = urljoin(base_url, link_href)
            
            # Lisame ainult samale domeenile jäävad lingid
            if urlparse(full_url).netloc == urlparse(base_url).netloc:
                links.append(f"{link_text}: {full_url}")
        
        # Eemaldame duplikaadid
        unique_links = list(set(links))
        
        if not unique_links:
            print("   ... Ei leidnud pealehelt ühtegi linki.")
            return base_url # Tagastame esialgse URL-i, kui linke pole

        # Koostame Geminile prompti
        prompt = f"""
        The following is a list of links found on the website {base_url}.
        Which of these URLs most likely leads to a page containing
        company staff, team, or contact information (e.g., "Contact", "Team", "About Us")?

        List of links (in the format "link text: URL"):
        ---
        {" :: ".join(unique_links[:100])} 
        ---
        
        Please respond with only the single, most suitable URL. If url includes "team", "tiim", "meeskond", "staff", "team members", "tootajad", "töötajad" then this is most likely the best URL. Url containing "meist" is probably not the best URL. If none are suitable, return: "NONE"
        """

        print(prompt)
        
        # Küsime Geminilt
        response = model.generate_content(prompt)
        suggested_url = response.text.strip()

        if "PUUDUB" in suggested_url or "http" not in suggested_url:
            print(f"   ... Gemini ei leidnud sobivat alamlehte, kasutame põhilehte: {base_url}")
            return base_url
        else:
            print(f"   ... Gemini soovitas kontaktileheks: {suggested_url}")
            return suggested_url

    except requests.exceptions.RequestException as e:
        print(f"   ... Viga pealehe allalaadimisel: {e}")
        return base_url # Vigade korral kasutame esialgset URL-i


def run_full_staff_search(base_url):
    """
    Searches for staff information on a company website using Gemini AI.
    
    Args:
        base_url: The company website URL
        
    Returns:
        List of dictionaries containing staff information, each with:
        - name: Staff member's name
        - role: Their role/title
        - email: Email address (or None)
        - phone: Phone number (or None)
        
        Returns None if there was an error fetching the website content.
    """
    # 1. Samm: Leia õige alamleht (nt /meeskond)
    contact_page_url = find_contact_page_url(base_url)
    
    # 2. Samm: Lae selle alamlehe sisu alla
    print(f"\nSamm 2: Sisu allalaadimine tuvastatud lehelt...")
    website_text = get_website_text(contact_page_url)
    
    if not website_text:
        print("Ei saanud veebilehe sisu kätte. Katkestan.")
        return None

    # 3. Samm: Koosta uus prompt ja saada Geminile
    prompt = f"""
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

    2. PERSONNEL / MARKETING:
       - 'HR Manager', 'Personalijuht'
       - 'Head of Marketing', 'Turundusjuht'
       - 'Head of Sales', 'Müügijuht'
    
    3. GENERAL CONTACT:
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
    {website_text[:30000]} 
    ---
    Finish analysis and return ONLY JSON.
    """
    
    print("\nSamm 3: Puhastatud teksti saatmine Geminile analüüsimiseks...")
    try:
        response = model.generate_content(prompt)
        
        print("\n--- Vastus (Manuaalse Sisuga) ---")
        # Puhastame vastuse, et näidata ainult JSON-i
        json_response = response.text.strip().lstrip("```json").lstrip("```").rstrip("```")
        
        # Parandame tagurpidi e-posti aadressid
        print("\nSamm 4: Parandan tagurpidi e-posti aadresse...")
        try:
            data = json.loads(json_response)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and 'email' in item and isinstance(item['email'], str):
                        if item['email'].startswith("ee."):
                            item['email'] = item['email'][::-1]
            fixed_json = json.dumps(data, indent=2, ensure_ascii=False)
            print(fixed_json)
            print("--------------------------------\n")
            return data
        except json.JSONDecodeError as e:
            print(f"Viga JSON-i parsimisel: {e}")
            print(f"Vastus: {json_response}")
            return None
    
    except Exception as e:
        print(f"Viga päringu tegemisel: {e}")
        return None
