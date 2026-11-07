# Food Diary Nutrient Tracker

A single-page teaching tool. Students enter a 3–5 day food diary and get daily averages for energy, macronutrients and 27 nutrients, compared with Health Canada's Dietary Reference Intakes (EAR, RDA/AI, UL, AMDR).

**Status: interface prototype.** The current page uses 18 hand-entered DEMO foods with approximate values. It is not Canadian Nutrient File data. Do not use the numbers for teaching or assessment yet.

## Features
- Food search, household measures or grams, meal tags, 3–5 days
- Averages and day-by-day totals; energy split vs AMDR
- Nutrients vs EAR, RDA/AI and UL, with status labels
- Data-coverage flags where the database has no value for a nutrient
- Top food sources for any nutrient
- Save/open the diary as a file; export results as CSV; print
- No server and no accounts: the diary stays in the student's browser

## Files
- `index.html` – the built page (open it in any browser)
- `template.html` – page source, with a placeholder for the food data
- `demo_data.json` – placeholder foods used for the prototype
- `build.py` – builds `index.html` from the demo data or from CNF CSV files

## Building with Canadian Nutrient File data
1. Download the CNF CSV files from the Open Government Portal (open.canada.ca).
2. Unzip into a folder, e.g. `cnf/`.
3. Run `python3 build.py --cnf cnf/ --version "CNF 2026"`.
4. Check the nutrient-matching report the script prints before using the page.

## Reference values
DRIs for adults 19–30 and 31–50 (male and female, not pregnant or lactating), from Health Canada's DRI tables. Sodium and potassium use the 2019 values.

## Data licence
Canadian Nutrient File: Health Canada, Open Government Licence – Canada.
