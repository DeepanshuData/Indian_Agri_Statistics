<img width="1092" height="700" alt="Screenshot 2026-10-01 233530" src="https://github.com/user-attachments/assets/cfc16c6f-f2f8-4128-9574-727b89f02344" />
<img width="1526" height="752" alt="Screenshot 2026-10-01 233430" src="https://github.com/user-attachments/assets/0147a611-d1e6-4146-adcb-9b012b3e369b" />
<img width="1190" height="692" alt="Screenshot 2026-10-01 233612" src="https://github.com/user-attachments/assets/7d3afb35-c39e-4c15-9570-1b50f8167792" />
 # Indian Agriculture Statistics

## Overview

This project organizes and analyzes agricultural statistics from India. It is intended to make commonly used agricultural data easier to explore, compare, and reuse for research, reporting, and data-driven decision-making.

## Objectives

- Collect and organize Indian agricultural statistics.
- Clean and standardize data for consistent analysis.
- Examine trends across crops, states, seasons, and years.
- Compare production, area, and productivity indicators.
- Present findings in a clear and reproducible form.

## Data Coverage

Depending on the dataset, the project may include:

- Crop-wise area, production, and yield
- State- and district-level agricultural indicators
- Food grains, pulses, oilseeds, commercial crops, and horticultural crops
- Year-wise and season-wise statistics
- Irrigation, land use, rainfall, and other supporting indicators

Always verify the source, period, units, and geographic level before using a dataset or result.

## Project Structure

```text
Indian_Agri_Statistics/
├── data/            # Raw and processed datasets
├── notebooks/       # Exploratory analysis and experiments
├── scripts/         # Data cleaning and analysis scripts
├── visualizations/  # Charts, plots, and exported figures
├── reports/         # Summaries and generated reports
└── Readme.md        # Project documentation
```

The folders above describe a recommended organization; use the directories available in the project as the authoritative structure.

## Streamlit Dashboard

The interactive dashboard is kept separate from the existing learning scripts in
`app/`. It reads `data/agridata.csv` (or the existing `Data/agridata.csv` folder),
and does not write changes to the source CSV.

Install the dashboard dependencies and start the app from the project root:

```bash
python -m pip install -r requirements.txt
streamlit run app/app.py
```

## Typical Workflow

1. Obtain data from the relevant official or publicly available source.
2. Preserve the original files and document their metadata.
3. Clean column names, missing values, duplicates, units, and category labels.
4. Validate totals and check for inconsistencies.
5. Perform exploratory analysis and calculate required indicators.
6. Generate tables and visualizations.
7. Record assumptions, limitations, and conclusions.

## Key Measures

- **Area:** cultivated or harvested area, usually reported in hectares.
- **Production:** quantity produced, with units depending on the source.
- **Yield/Productivity:** production per unit of area.
- **Growth rate:** percentage change between comparable periods.
- **Share:** contribution of a crop or region to a selected total.

Use the units and definitions provided by the source rather than assuming that similarly named fields are directly comparable.

## Data Quality and Reproducibility

- Keep raw data unchanged.
- Record source URLs, download dates, and publication details.
- Document transformations and assumptions.
- Use consistent units and year formats.
- Check missing, duplicated, and anomalous observations.
- Update analysis when source data is revised.

## Results

The analysis can be used to identify agricultural trends, regional differences, changes in crop performance, and relationships between area, production, and productivity. Specific findings should be reported alongside the source and coverage period of the underlying data.

## Limitations

Results may be affected by differences in definitions, revisions to official data, missing observations, changes in administrative boundaries, rounding, and differences in reporting units. Conclusions should therefore be interpreted within the scope of the selected datasets.

## Data Sources

Add the exact sources used in this project here, including dataset names, URLs, publication years, and licenses. Suitable official sources may include publications and portals from the Government of India, the Ministry of Agriculture and Farmers Welfare, the Directorate of Economics and Statistics, and state government departments.

## License and Attribution

Add the project license and attribution requirements for each dataset here. Credit all original data providers and comply with their terms of use.
<img width="1190" height="692" alt="Screenshot 2026-10-01 233612" src="https://github.com/user-attachments/assets/cb332dfc-a0bd-4f9e-bfbc-8f3f2ca333b2" />
<img width="1092" height="700" alt="Screenshot 2026-10-01 233530" src="https://github.com/user-attachments/assets/f6a1cd47-6f57-4069-9609-05095ee75956" />
<img width="1526" height="752" alt="Screenshot 2026-10-01 233430" src="https://github.com/user-attachments/assets/fe760610-dff8-4f6b-bda5-2326b0798325" />
