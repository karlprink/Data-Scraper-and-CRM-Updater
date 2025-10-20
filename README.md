# Data-Scraper-and-CRM-Updater Release Notes

## Overview

This release completes the implementation of the Auto-Fill use case, which enables collaboration managers to automatically populate company details in the CRM system by entering a valid Business Registry Code.
The feature reduces manual data entry and ensures accurate, up-to-date information retrieved directly from the Estonian Business Register. The process is initiated by clicking a dynamic link, which provides immediate feedback in a new browser window.

## Implemented Functionality

* The system retrieves company information based on the entered Business Registry Code.
* When the Vercel link is clicked, the corresponding company fields are automatically populated.
* The system provides clear success or error feedback in a new browser window that opens after the link is clicked.

## Main Success Scenario

1.  The collaboration manager enters a valid Business Registry Code in the appropriate field.
2.  The manager clicks the Vercel link.
3.  The system fetches company data and fills in all relevant fields in the CRM entry.
4.  A new browser window opens, displaying a success message.

## Alternate Scenarios

### 1. Invalid or Malformed Registry Code:

* **Flow:** The collaboration manager enters a registry code in an incorrect format.
* **System Response:** After the link is clicked, a new browser window opens displaying an error message. The Notion page remains unchanged.

### 2. Registry Code Not Found:

* **Flow:** The collaboration manager enters a validly formatted registry code, but the company is not found in the Business Register data.
* **System Response:** After the link is clicked, a new browser window opens displaying an error message indicating the company was not found. The Notion page remains unchanged.

## Preconditions

* The collaboration manager has opened the CRM page and started a new company entry.

## Postconditions

* **On Success:** The selected entry in the CRM has its fields populated.
* **On Failure:** The selected entry in the CRM is unchanged.
* No other entries or data in the system are modified.

## Testing Summary

Verified full workflow from link click to field population, including success and error feedback scenarios in the pop-up window.

## Remaining Bugs and Known Issues

* **Suboptimal User Experience for Trigger:** The current method for triggering the autofill requires the user to click a link, which opens a new browser tab. The ideal solution is a button that runs the process silently in the background without navigating the user away from their Notion page. Research for a better, low-latency solution is ongoing.
    * For more details, see GitHub Issue: **#24**

## Status
**Use Case 1 — Auto-Fill** main and alternate scenarios are implemented, tested, and deployed as part of the current release.
