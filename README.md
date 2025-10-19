# Data-Scraper-and-CRM-Updater

## CLI kasutamine

Installi sõltuvused ja käivita CLI:

```bash
pip install -r requirements.txt
python main.py --help
```

Kaks režiimi:

- Registrikoodi järgi sünkroonimine CSV-st Notioni (lisab või uuendab kirjet):

```bash
python main.py --regcode 12345678
```

- Täida olemasoleva Notioni lehe andmed lehe `id()` põhjal (loe "Registrikood" lehelt ja uuenda sama lehte):

```bash
python main.py --page-id a1b2c3d4e5f6g7h8i9j0
```

Veendu, et `config.yaml` sisaldab `notion.token`, `notion.database_id` ja `ariregister.csv_url` seadeid.




## Release Notes

### Overview
This release completes the implementation of the **Auto-Fill** use case, which enables collaboration managers to automatically populate company details in the CRM system by entering a valid Business Registry Code.  
The feature reduces manual data entry and ensures accurate, up-to-date information retrieved directly from the Estonian Business Register.

### Implemented Functionality
- The system retrieves company information based on the entered Business Registry Code.  
- When **“Auto-Fill”** is clicked, the corresponding company fields are automatically populated.  
- Clear user feedback messages confirm successful completion or report any issues.

### Main Success Scenario
1. The collaboration manager enters a valid Business Registry Code.  
2. The manager clicks **“Auto-Fill.”**  
3. The system fetches company data and fills in all fields in the selected CRM entry.  
4. The system notifies the manager that all fields were successfully filled.

### Alternate Scenarios
- **Invalid or missing registry code:**  
  The system detects the error and displays a message indicating that the code is invalid or missing.  
- **Partial data retrieval:**  
  If some information cannot be scraped, the system fills only the available fields and informs the manager that certain fields remain empty.

### Preconditions
- The Notion plugin is installed.  
- The collaboration manager has opened the CRM page, selected a company entry, and accessed its details.

### Postconditions
- The selected entry in the CRM has its fields populated with retrieved company data.  
- No other entries or data in the system are modified.

### Testing Summary
- Verified full workflow from input submission to field population.  
- Tested error handling for invalid and missing codes.  
- Confirmed correct notifications for partial and complete autofill outcomes.

### Status
**Use Case 1 — Auto-Fill** is fully implemented, tested, and deployed as part of the current release.

