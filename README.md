# Food Diary Nutrient Tracker

A single-page teaching tool. Students enter a 3–5 day food diary and get daily averages for energy, macronutrients and 27 nutrients, compared with Health Canada's Dietary Reference Intakes (EAR, RDA/AI, UL, AMDR).

**Status: pilot version.** Generic foods: Health Canada's Canadian Nutrient File 2026 (5,993 foods). Packaged products: about 68,700 branded Canadian products from Open Food Facts label data, after automatic plausibility checks remove entries whose values are inconsistent (e.g., per-serving values typed into per-100 g fields).

## Features
- Activity log (24 hours per day) using the 2024 Adult Compendium of Physical Activities: 183 common student activities, with all 1,111 compendium activities searchable
- Resting energy (Mifflin-St Jeor), physical activity level (PAL), and Estimated Energy Requirement from the 2023 NASEM DRI equations; reported intake compared with EER
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
- `build.py` – builds `index.html` from the demo data or CNF CSV files, plus Open Food Facts
- `data/compendium_2024.json` – 2024 Adult Compendium activities (MET values unchanged)
- `data/activities_curated.json` – student-friendly labels for 183 common activities
- `data/off_canada.json` – Canadian products extracted from Open Food Facts
- `scripts/fetch_off_canada.py` and `.github/workflows/fetch-data.yml` – GitHub job that refreshes the Open Food Facts extract (run it from the Actions tab)

## Building with Canadian Nutrient File data
1. Download the CNF CSV files from the Open Government Portal (open.canada.ca).
2. Unzip into a folder, e.g. `cnf/`.
3. Run `python3 build.py --cnf cnf/ --version "CNF 2026" --off data/off_canada.json`.
4. Check the nutrient-matching report the script prints before using the page.

## Reference values
DRIs for adults 19–30 and 31–50 (male and female, not pregnant or lactating), from Health Canada's DRI tables. Sodium and potassium use the 2019 values.

## Data licence
- Canadian Nutrient File: Health Canada, Open Government Licence – Canada.
- Open Food Facts: © Open Food Facts contributors, Open Database License (ODbL). The extract in `data/` is shared under the same licence.

Packaged products carry label data only: energy, fats, carbohydrate, sugars, fibre, protein, sodium, and (for about 45%) cholesterol, potassium, calcium and iron.

- 2024 Adult Compendium of Physical Activities: Herrmann SD, Willis EA, Ainsworth BE, et al. J Sport Health Sci 2024;13(1):6–12. https://pacompendium.com/ (free for educational use; MET values unchanged).
- Energy equations: National Academies of Sciences, Engineering, and Medicine. Dietary Reference Intakes for Energy. 2023. doi:10.17226/26818. Resting energy: Mifflin MD, et al. Am J Clin Nutr 1990;51:241–7.
