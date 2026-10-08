# 🌾 AgriProfit Intelligence

### Turning agricultural data into profitable decisions

AgriProfit Intelligence is an agriculture analytics platform that brings crop
production, historical yields, reference costs and prices, market comparisons,
and weather forecasts into one interactive application. It helps farmers,
analysts, and agri-businesses explore crop choices, estimate profitability, and
compare potential selling destinations.

> A high-yield crop is not automatically the most profitable crop. Better
> decisions consider yield, cost, price, location, season, and risk together.

---

## 🎯 The Problem

Agricultural information is often spread across separate datasets and tools.
Yield history alone cannot answer whether a crop is affordable to grow, what
its expected return might be, or whether a different market could improve the
sale price after transport.

The decision is not simply:

> "Which crop produced the most?"

It is:

> "Which available crop could offer a suitable return for this location,
> season, budget, and level of risk?"

## 💡 The Solution

The application combines the included agriculture statistics with supplied
crop-economics and market reference data, and can retrieve a five-day forecast
from Open-Meteo. Interactive tools turn these inputs into estimates and
comparisons, while making the assumptions and data coverage visible.

## 🚀 Key Capabilities

### 1. Explore agricultural statistics

- Filter records by state, district, crop, season, and year.
- Review area, production, yield, and record-count summaries.
- Visualize crop area by state, production by crop, area trends, and state-by-crop
  area.

### 2. What Should I Grow?

Rank crops with historical district and season yields, land size, budget,
reference crop economics, and irrigation availability. Optionally include the
current five-day weather-risk category in the ranking.

### 3. Profitability

Estimate production, revenue, costs, profit, ROI, and price risk for a crop.
Land, sale price, and cost per acre are editable assumptions.

```text
Expected production = Historical yield × Land area
Expected revenue    = Expected production × Assumed selling price
Expected profit     = Expected revenue − Estimated cost
ROI                 = Expected profit ÷ Estimated cost × 100
```

The application converts acres to hectares and tonnes to kilograms when
combining the agriculture yield data with prices per kilogram.

### 4. Where Should I Sell?

Compare destinations listed in the supplied market data using price, distance,
estimated transport cost, and net realization for the selected quantity.

### 5. Weather Risk

Look up a district using Open-Meteo geocoding, view its five-day forecast, and
summarize rainfall, maximum precipitation probability, and a simple risk
category.

## 🧭 How the Application Works

```text
Agriculture CSV ──┐
Crop economics ───┼──> Pandas calculations ──> Estimates and rankings ──┐
Market reference ─┘                                                      ├──> Streamlit dashboard
District selection ──> Open-Meteo geocoding and forecast ────────────────┘
```

## 🛠 Technology Stack

- **Python** for application and analytics code
- **Pandas** for CSV data handling and calculations
- **Streamlit** for the interactive web application
- **Plotly** for interactive charts
- **Requests** for Open-Meteo API calls
- **CSV** for agriculture statistics and reference economics/market data

## ▶️ Run Locally

From the project root, install the dependencies and start the dashboard:

```bash
python -m pip install -r requirements.txt
streamlit run app/app.py
```

Open the local URL printed by Streamlit (usually
`http://localhost:8501`). The main agriculture dataset is read from
`Data/agridata.csv` or `data/agridata.csv`.

Weather lookup requires an internet connection. Crop recommendations and
profitability require `Data/crop_economics.csv`; market comparison requires
`Data/market_data.csv`.

## 🗂 Project Structure

```text
Indian_Agri_Statistics/
├── app/
│   ├── app.py                       # Streamlit dashboard and tools
│   ├── recommendation_engine.py     # Crop yield, risk, and ranking logic
│   ├── profitability_engine.py     # Profit and ROI calculations
│   ├── market_engine.py             # Net market realization calculations
│   ├── weather_engine.py            # Geocoding, forecast, and weather risk
│   └── styles.css                   # Dashboard styling
├── Data/
│   ├── agridata.csv                 # Historical crop statistics
│   ├── crop_economics.csv           # Reference prices, costs, and risk inputs
│   ├── market_data.csv              # Reference destination prices and transport
│   └── district_coordinates.csv     # Optional coordinates data
├── requirements.txt
└── Readme.md
```

The repository also includes standalone Python analysis scripts and SQL
examples.

## 📌 Data, Assumptions & Limitations

- The agriculture CSV contains state, district, crop, year, season, area,
  production, and yield fields. Check the source, coverage period, and units
  before using results for operational decisions.
- The included economics and market values are reference inputs, not guaranteed
  current prices or quotes. Market comparisons are limited to destinations and
  crops present in `Data/market_data.csv`.
- Profitability and recommendations are estimates based on historical average
  yield and the selected assumptions. They do not account for every factor
  affecting realized farm returns.
- Weather risk is a simple indicator based on five-day rainfall and precipitation
  probability thresholds; it is not an agronomic forecast or a substitute for
  local advice.
- Results depend on data quality, units, administrative boundaries, and the
  coverage of the available datasets. Confirm assumptions before making
  financial or planting decisions.
- Weather services may be unavailable or return no result for a selected
  location.

Document dataset publishers, source URLs, download dates, and applicable
licenses alongside future data updates.

## 🔬 Current Status

### Phase 1 — Analytics foundation

- [x] Python data processing and CSV ingestion
- [x] Agriculture data filtering and summaries
- [x] Pandas groupby, merge, and pivot analysis examples
- [x] Interactive agriculture visualizations
- [x] Streamlit dashboard

### Phase 2 — Decision tools

- [x] Crop profitability estimates
- [x] Crop ranking with yield, economics, budget, and irrigation inputs
- [x] Optional weather-risk input to crop ranking
- [x] Market destination comparison
- [x] Five-day weather risk view

### Phase 3 — Potential next steps

- [ ] Automated, documented ingestion from verified data sources
- [ ] Broader and regularly updated crop economics and market coverage
- [ ] Persistent data storage and service API
- [ ] User accounts and production deployment
- [ ] Validated forecasting models and decision support

## 📈 Future Vision

AgriProfit Intelligence aims to grow from an agricultural analytics dashboard
into a decision-support platform. The goal is to connect reliable data with
clear assumptions, helping users move from understanding what happened to
evaluating what may be a better next decision.

## 👨‍💻 Author

Built as a practical application of Python, data processing, analytics,
visualization, API integration, and business-oriented decision support.

### Dashboard screenshots

<img width="1092" height="700" alt="Agriculture dashboard screenshot" src="https://github.com/user-attachments/assets/cfc16c6f-f2f8-4128-9574-727b89f02344" />
<img width="1526" height="752" alt="Agriculture dashboard screenshot" src="https://github.com/user-attachments/assets/0147a611-d1e6-4146-adcb-9b012b3e369b" />
<img width="1190" height="692" alt="Agriculture dashboard screenshot" src="https://github.com/user-attachments/assets/7d3afb35-c39e-4c15-9570-1b50f8167792" />
