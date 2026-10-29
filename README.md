# Formula E Gen3 Evo — Pit-Wall Telemetry & Driver Performance Analyzer

A real-time motorsport telemetry microservice and interactive Pit-Wall Engineering Dashboard built with **FastAPI**, **Pydantic v2**, **Matplotlib**, and **Jinja2**.

Designed around the **FIA Formula E Gen3 Evo** technical regulations, this project evaluates lap-by-lap driver energy management—specifically MGU regenerative braking harvest in heavy braking zones and lift-and-coast execution—to compute an overall **Efficiency Score (0–100)**, detect hardware sensor anomalies, render dark-themed pit-wall telemetry charts, and generate actionable race engineering feedback.

---

## Key Features

- **Gen3 Evo Physical Constraint & Sensor Fault Detection**
  - Enforces the Formula E Gen3 Evo **600 kW** combined front + rear MGU maximum regenerative braking limit.
  - Automatically flags inverter/current sensor spikes (`> 600 kW`) with `sensor_fault_detected: true` (`sensor_error: true`), caps physical calculations at `600 kW`, and alerts the race engineer.
- **Heavy Braking Zone Energy Recovery Analysis (50 pts)**
  - Evaluates peak regenerative braking power in primary heavy braking zones (**Turn 3** and **Turn 13**) against the **$\ge 500\text{ kW}$** target threshold.
  - Awards **50 points** when both zones meet target, **25 points** for single-zone recovery, and **0 points** when both fall short.
- **Lift-and-Coast Energy Management Scoring (50 pts)**
  - Evaluates pre-braking throttle lift distance against the **$\ge 50\text{ m}$** optimal target (**50 points**), **25–49 m** partial window (**25 points**), and **$< 25\text{ m}$** deficit (**0 points**).
- **Headless Dark-Mode Telemetry Visualization**
  - Uses headless `Matplotlib` (`Agg` backend) to stream high-contrast dark-themed PNG charts (`/api/v1/chart`) and base64-embedded dashboard visuals featuring electric cyan (`#00f0ff`), volt green (`#39ff14`), a gold **500 kW Target** line (`#ffd700`), and a crimson **600 kW Max Physical Limit** line (`#ff3366`).
- **Interactive Pit-Wall Web Dashboard**
  - Responsive dark-mode UI (`/dashboard`) with one-click telemetry presets (*Optimal Lap*, *Marginal Coast*, *650 kW Sensor Fault*, *Under-Regen Lap*), live sliders, KPI cards, and real-time race engineer feedback.

---

## Architecture & Project Structure

```text
fe-driver-performance/
├── main.py                  # FastAPI application, scoring engine, and Matplotlib chart renderer
├── models.py                # Pydantic v2 request/response schemas & flexible telemetry normalization
├── templates/
│   └── dashboard.html       # Interactive Pit-Wall Telemetry Dashboard (Jinja2 + Fetch API)
├── .agents/
│   └── skills/
│       └── driver-evaluation/
│           └── SKILL.md     # Domain rules for Formula E Gen3 Evo telemetry evaluation
├── GEMINI.md                # Pit-wall engineering standards & container compatibility rules
├── requirements.txt         # Python dependencies
└── README.md                # Project documentation
```

---

## Evaluation & Scoring Rules

| Component | Condition | Points Awarded |
| :--- | :--- | :---: |
| **Heavy Braking Regen** *(Turn 3 & Turn 13)* | Both Turn 3 and Turn 13 achieve $\ge 500\text{ kW}$ | **50** |
| | Either Turn 3 or Turn 13 achieves $\ge 500\text{ kW}$ | **25** |
| | Both Turn 3 and Turn 13 are $< 500\text{ kW}$ | **0** |
| **Lift-and-Coast Distance** | Coasting initiated $\ge 50\text{ m}$ before braking zone | **50** |
| | Coasting initiated between $25\text{ m}$ and $49\text{ m}$ | **25** |
| | Coasting initiated $< 25\text{ m}$ | **0** |
| **Physical Cap & Fault Check** | Reported regen $> 600\text{ kW}$ | Capped at `600 kW` & flags `sensor_fault_detected = true` |

### Performance Ratings
- **`EXCELLENT`**: Efficiency Score $\ge 80$
- **`OPTIMAL`**: Efficiency Score $50 - 79$
- **`NEEDS_IMPROVEMENT`**: Efficiency Score $< 50$

---

## Getting Started

### 1. Clone the Repository & Set Up Environment

```bash
git clone https://github.com/<your-username>/fe-driver-performance.git
cd fe-driver-performance

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run the FastAPI Server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open your browser to:
- **Interactive Pit-Wall Dashboard**: [http://localhost:8000/dashboard](http://localhost:8000/dashboard)
- **Interactive OpenAPI Docs (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## API Reference

### 1. Evaluate Lap Telemetry (`POST /api/v1/evaluate`)

Evaluates driver telemetry metrics and returns the efficiency score, categorical rating, sensor fault status, and actionable engineering feedback.

**Example Request:**
```bash
curl -X POST http://localhost:8000/api/v1/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "driver_id": "GEN3-EVO-01",
    "lap_number": 12,
    "turn_3_regen_kw": 545.0,
    "turn_13_regen_kw": 520.0,
    "lift_and_coast_m": 54.0
  }'
```

**Example Response (`200 OK`):**
```json
{
  "efficiency_score": 100,
  "rating": "EXCELLENT",
  "sensor_fault_detected": false,
  "sensor_error": false,
  "feedback": [
    "Heavy Braking Recovery Optimal: Achieved >= 500 kW target in both Turn 3 (545 kW) and Turn 13 (520 kW).",
    "Lift-and-Coast Optimal: Coasting initiated at 54m (meets >= 50m target before braking threshold)."
  ],
  "driver_id": "GEN3-EVO-01",
  "lap_number": 12,
  "capped_peak_regen_kw": 545.0,
  "capped_turn_3_regen_kw": 545.0,
  "capped_turn_13_regen_kw": 520.0,
  "braking_score": 50,
  "lift_and_coast_score": 50
}
```

### 2. Stream Telemetry Chart (`GET /api/v1/chart`)

Generates and streams a dark-mode PNG bar chart of circuit braking zone regeneration power vs. the 500 kW target and 600 kW physical limit.

```bash
curl -G http://localhost:8000/api/v1/chart \
  --data-urlencode "driver_id=GEN3-EVO-01" \
  --data-urlencode "lap_number=12" \
  --data-urlencode "turn_3_regen_kw=545" \
  --data-urlencode "turn_13_regen_kw=520" \
  --data-urlencode "lift_and_coast_m=54" \
  --output telemetry_chart.png
```

### 3. Interactive Dashboard (`GET /dashboard`)

Renders the full Pit-Wall Driver Performance Dashboard with interactive sliders, scenario presets, live chart updates, and KPI cards.

---

## Tech Stack

- **Backend Framework**: [FastAPI](https://fastapi.tiangolo.com/) & [Uvicorn](https://www.uvicorn.org/)
- **Data Validation**: [Pydantic v2](https://docs.pydantic.dev/)
- **Visualization**: [Matplotlib](https://matplotlib.org/) (Headless `Agg` renderer)
- **Templating & UI**: [Jinja2](https://jinja.palletsprojects.com/), HTML5, CSS3, Vanilla JS
- **Testing**: [Pytest](https://docs.pytest.org/) & [HTTPX](https://www.python-httpx.org/)
# fe-driver-performance
# fe-driver-performance
# fe-driver-performance
# fe-driver-performance
# fe-driver-performance
