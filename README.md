# Data-Scraper-and-CRM-Updater

## Release Notes

### Overview
This release completes the implementation of the **Auto-Fill** use case, which enables collaboration managers to automatically populate company details in the CRM system by entering a valid Business Registry Code.  
The feature reduces manual data entry and ensures accurate, up-to-date information retrieved directly from the Estonian Business Register.

### Implemented Functionality
- The system retrieves company information based on the entered Business Registry Code.  
- When **“Auto-Fill”** is clicked, the corresponding company fields are automatically populated.  

### Main Success Scenario
1. The collaboration manager enters a valid Business Registry Code.  
2. The manager clicks **“Auto-Fill.”**  
3. The system fetches company data and fills in all fields in the selected CRM entry.  
4. If the registry code is correct, then the corresponding fields are filled.

### Preconditions
- The collaboration manager has opened the CRM page and started a new company entry.

### Postconditions
- The selected entry in the CRM has its fields populated with retrieved company data from business register.  
- No other entries or data in the system are modified.

### Testing Summary
- Verified full workflow from input submission to field population.  

### Status
**Use Case 1 — Auto-Fill** main scenario is implemented, tested, and deployed as part of the current release.

