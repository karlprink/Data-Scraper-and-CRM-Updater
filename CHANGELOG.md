## Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-10-17

#### Iteration 2

This is the initial release of the **Data-Scraper-and-CRM-Updater**.

This release completes the implementation of the **Auto-Fill use case**, which enables collaboration managers to automatically populate company details in the CRM system by entering a valid Business Registry Code. The feature reduces manual data entry and ensures accurate, up-to-date information retrieved directly from the Estonian Business Register.

### Added

- **Core Auto-Fill Feature:** Users can now automatically populate company fields by entering a Business Registry Code and clicking an "Auto-Fill" trigger.
- **Backend Integration:** The system successfully retrieves (scrapes) company information from the Estonian Business Register.
- **Notion Integration:** The system populates the corresponding fields (properties) on the correct Notion company page.
- **End-to-End Workflow:** The main success scenario (enter code -> click -> data appears) is fully implemented, tested, and deployed.

## [0.2.0] - 2025-11-20

#### Iteration 3

### Added
- **AI Staff Scraper:** Introduced a new Vercel function (`/api/update-staff`) that uses Google Gemini AI (1.5 Flash) to analyze company websites.
    - Extracts key personnel (CEO, HR Manager, Sales/Marketing heads).
    - Automatically creates entries in the new **Contacts** database.
    - **Smart Linking:** Programmatically links new contacts to the correct Company page via Notion Relations.
    - **Duplicate Prevention:** Updates existing contacts based on email/name matching instead of creating duplicates; removes contacts no longer found on the website.
      
### Changed
- **Database Architecture:**
    - Added a new `Contacts` database schema.
    - Updated `Companies` database schema to include a Relation property to `Contacts`.

### Technical
- **Gemini Prompt Engineering:** Implemented a robust prompt strategy to force Gemini to return strict JSON arrays, handling empty results and "obfuscated" emails (e.g., reversed text) gracefully.
