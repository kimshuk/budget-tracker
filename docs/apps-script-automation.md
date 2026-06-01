# Google Sheets Automation

Use this when you want edits in `merchant_categories` to update `transactions` and `dashboard` without running `python import_cmd.py`.

## Install

1. Open the budget spreadsheet.
2. Go to **Extensions > Apps Script**.
3. Replace the default script with the contents of `apps_script/Code.gs` from this repo.
4. Save the script.
5. Reload the spreadsheet.
6. In the spreadsheet menu, open **Budget Tracker > Install automation**.
7. Approve the requested spreadsheet permissions.

After installation, editing column B in `merchant_categories` triggers:

1. Sync matching `transactions.category` values from `merchant_categories`.
2. Rebuild `dashboard`.
3. Recreate the recent two-month category bar chart.

## Manual Rebuild

Use **Budget Tracker > Sync categories and rebuild dashboard** if you want to refresh the dashboard manually.

## Python Still Handles Imports

Keep using `python import_cmd.py` for importing exported bank/card/pay files. The Apps Script automation only handles live spreadsheet edits after transactions are already imported.

## Notes

- The script is bound to one spreadsheet.
- The install step creates an installable `onEdit` trigger for that spreadsheet.
- If you replace or copy the spreadsheet, run **Budget Tracker > Install automation** again in the new spreadsheet.
