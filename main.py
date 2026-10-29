import base64
import io
import os
from typing import Optional

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from models import EvaluationResponse, TelemetryRequest

MAX_REGEN_KW = 600.0
TARGET_REGEN_KW = 500.0
TARGET_COAST_M = 50.0
MIN_PARTIAL_COAST_M = 25.0

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

app = FastAPI(
    title="Formula E Gen3 Evo Pit-Wall Telemetry Service",
    description=(
        "Evaluates Formula E Gen3 Evo driver lap telemetry against braking zone "
        "regeneration limits and lift-and-coast energy management targets."
    ),
    version="1.0.0",
)


def evaluate_driver_telemetry(payload: TelemetryRequest) -> EvaluationResponse:
    """Evaluate Formula E Gen3 Evo telemetry according to pit-wall engineering rules."""
    raw_t3 = float(payload.turn_3_regen_kw)
    raw_t13 = float(payload.turn_13_regen_kw)
    raw_peak = float(
        payload.peak_regen_kw
        if payload.peak_regen_kw is not None
        else max(raw_t3, raw_t13)
    )
    raw_peak = max(raw_peak, raw_t3, raw_t13)

    # 1. Physical Regeneration Constraints (600 kW Max Cap & Sensor Fault Detection)
    sensor_fault_detected = (
        raw_t3 > MAX_REGEN_KW or raw_t13 > MAX_REGEN_KW or raw_peak > MAX_REGEN_KW
    )
    capped_t3 = min(raw_t3, MAX_REGEN_KW)
    capped_t13 = min(raw_t13, MAX_REGEN_KW)
    capped_peak = min(raw_peak, MAX_REGEN_KW)

    feedback = []
    if sensor_fault_detected:
        feedback.append(
            f"SENSOR FAULT DETECTED: Reported peak regeneration ({raw_peak:.0f} kW) "
            f"exceeds the Formula E Gen3 Evo 600 kW physical limit. Value capped at 600 kW; "
            f"inspect MGU inverter current sensor."
        )

    # 2. Heavy Braking Energy Recovery (Turn 3 and Turn 13, Target >= 500 kW)
    t3_hit = capped_t3 >= TARGET_REGEN_KW
    t13_hit = capped_t13 >= TARGET_REGEN_KW

    if t3_hit and t13_hit:
        braking_score = 50
        feedback.append(
            f"Heavy Braking Recovery Optimal: Achieved >= 500 kW target in both "
            f"Turn 3 ({capped_t3:.0f} kW) and Turn 13 ({capped_t13:.0f} kW)."
        )
    elif t3_hit or t13_hit:
        braking_score = 25
        if not t3_hit:
            feedback.append(
                f"Turn 3 Under-Recovery: Peak regen of {capped_t3:.0f} kW is below the "
                f"500 kW target. Increase initial brake pressure and rear regen map bias at Turn 3."
            )
        if not t13_hit:
            feedback.append(
                f"Turn 13 Under-Recovery: Peak regen of {capped_t13:.0f} kW is below the "
                f"500 kW target. Maximize MGU energy harvest in Turn 13 heavy braking."
            )
    else:
        braking_score = 0
        feedback.append(
            f"Critical Braking Energy Deficit: Both Turn 3 ({capped_t3:.0f} kW) and "
            f"Turn 13 ({capped_t13:.0f} kW) missed the 500 kW regeneration threshold."
        )

    # 3. Lift-and-Coast Energy Management (Target >= 50m, Partial 25m-49m)
    coast_m = float(payload.lift_and_coast_m)
    if coast_m >= TARGET_COAST_M:
        lift_and_coast_score = 50
        feedback.append(
            f"Lift-and-Coast Optimal: Coasting initiated at {coast_m:.0f}m "
            f"(meets >= 50m target before braking threshold)."
        )
    elif coast_m >= MIN_PARTIAL_COAST_M:
        lift_and_coast_score = 25
        feedback.append(
            f"Lift-and-Coast Marginal: Coasting distance of {coast_m:.0f}m is in the "
            f"25-49m partial window. Lift off throttle {TARGET_COAST_M - coast_m:.0f}m earlier."
        )
    else:
        lift_and_coast_score = 0
        feedback.append(
            f"Lift-and-Coast Deficit: Coasting distance of {coast_m:.0f}m is below the 25m "
            f"minimum. Initiate lift-and-coast at least 50m before heavy braking zones."
        )

    # 4. Efficiency Score & Rating Classification
    efficiency_score = int(braking_score + lift_and_coast_score)
    if efficiency_score >= 80:
        rating = "EXCELLENT"
    elif efficiency_score >= 50:
        rating = "OPTIMAL"
    else:
        rating = "NEEDS_IMPROVEMENT"

    return EvaluationResponse(
        efficiency_score=efficiency_score,
        rating=rating,
        sensor_fault_detected=sensor_fault_detected,
        sensor_error=sensor_fault_detected,
        feedback=feedback,
        driver_id=payload.driver_id,
        lap_number=payload.lap_number,
        capped_peak_regen_kw=capped_peak,
        capped_turn_3_regen_kw=capped_t3,
        capped_turn_13_regen_kw=capped_t13,
        braking_score=braking_score,
        lift_and_coast_score=lift_and_coast_score,
    )


def generate_telemetry_chart_buffer(
    turn_3_regen_kw: float = 540.0,
    turn_13_regen_kw: float = 515.0,
    lift_and_coast_m: float = 52.0,
    driver_id: str = "GEN3-EVO-01",
    lap_number: int = 1,
) -> io.BytesIO:
    """Render dark-themed Formula E lap regeneration telemetry PNG image stream."""
    plt.style.use('dark_background')

    capped_t3 = min(max(turn_3_regen_kw, 0.0), MAX_REGEN_KW)
    capped_t13 = min(max(turn_13_regen_kw, 0.0), MAX_REGEN_KW)
    fault_detected = turn_3_regen_kw > MAX_REGEN_KW or turn_13_regen_kw > MAX_REGEN_KW

    zones = [
        "Turn 1",
        "Turn 3 (Heavy)",
        "Turn 6",
        "Turn 9",
        "Turn 13 (Heavy)",
        "Turn 16",
    ]
    regen_values = [
        310.0,
        capped_t3,
        275.0,
        345.0,
        capped_t13,
        290.0,
    ]
    # Electric cyan (#00f0ff) for standard braking zones and volt green (#39ff14) for primary heavy zones
    bar_colors = [
        "#00f0ff",
        "#39ff14",
        "#00f0ff",
        "#00f0ff",
        "#39ff14",
        "#00f0ff",
    ]

    fig, ax = plt.subplots(figsize=(10, 5.2), dpi=120)
    fig.patch.set_facecolor("#0a0e17")
    ax.set_facecolor("#0f1624")

    bars = ax.bar(
        zones,
        regen_values,
        color=bar_colors,
        edgecolor="#ffffff",
        linewidth=0.8,
        width=0.55,
    )

    # Reference lines: 500 kW Target (Gold #ffd700) and 600 kW Max Physical Limit (Red #ff3366)
    ax.axhline(
        TARGET_REGEN_KW,
        color="#ffd700",
        linestyle="--",
        linewidth=2.0,
        label="Target Regen (500 kW)",
    )
    ax.axhline(
        MAX_REGEN_KW,
        color="#ff3366",
        linestyle="--",
        linewidth=2.0,
        label="Max Physical Limit (600 kW)",
    )

    for bar, val in zip(bars, regen_values):
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            val + 12.0,
            f"{val:.0f} kW",
            ha="center",
            va="bottom",
            color="#e6edf3",
            fontsize=9.5,
            fontweight="bold",
        )

    title_suffix = " [SENSOR FAULT CAPPED @ 600 kW]" if fault_detected else ""
    ax.set_title(
        f"Formula E Gen3 Evo Lap Telemetry — {driver_id} (Lap {lap_number}) | "
        f"Lift & Coast: {lift_and_coast_m:.0f}m{title_suffix}",
        color="#00f0ff",
        fontsize=12,
        fontweight="bold",
        pad=14,
    )
    ax.set_ylabel("Regenerative Braking Power (kW)", color="#c9d1d9", fontsize=10.5)
    ax.set_xlabel("Circuit Braking Zones", color="#c9d1d9", fontsize=10.5)
    ax.set_ylim(0, 680)
    ax.grid(axis="y", linestyle=":", alpha=0.3, color="#8b949e")
    ax.legend(loc="upper right", facecolor="#161b22", edgecolor="#30363d")

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    """Redirect root requests to the interactive pit-wall dashboard."""
    return RedirectResponse(url="/dashboard")


@app.post("/api/v1/evaluate", response_model=EvaluationResponse)
async def evaluate_endpoint(payload: TelemetryRequest) -> EvaluationResponse:
    """Evaluate driver lap telemetry and return efficiency score, rating, and feedback."""
    return evaluate_driver_telemetry(payload)


@app.get("/api/v1/chart")
async def chart_endpoint(
    turn_3_regen_kw: float = Query(default=540.0, ge=0.0),
    turn_13_regen_kw: float = Query(default=515.0, ge=0.0),
    peak_regen_kw: Optional[float] = Query(default=None, ge=0.0),
    lift_and_coast_m: float = Query(default=52.0, ge=0.0),
    driver_id: str = Query(default="GEN3-EVO-01"),
    lap_number: int = Query(default=1, ge=1),
) -> StreamingResponse:
    """Stream a Matplotlib PNG chart of Formula E lap regeneration telemetry."""
    t3 = peak_regen_kw if peak_regen_kw is not None and turn_3_regen_kw == 540.0 else turn_3_regen_kw
    t13 = peak_regen_kw if peak_regen_kw is not None and turn_13_regen_kw == 515.0 else turn_13_regen_kw
    buf = generate_telemetry_chart_buffer(
        turn_3_regen_kw=t3,
        turn_13_regen_kw=t13,
        lift_and_coast_m=lift_and_coast_m,
        driver_id=driver_id,
        lap_number=lap_number,
    )
    return StreamingResponse(buf, media_type="image/png")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_endpoint(
    request: Request,
    driver_id: str = Query(default="GEN3-EVO-01"),
    lap_number: int = Query(default=12, ge=1),
    turn_3_regen_kw: float = Query(default=545.0, ge=0.0),
    turn_13_regen_kw: float = Query(default=520.0, ge=0.0),
    lift_and_coast_m: float = Query(default=54.0, ge=0.0),
) -> HTMLResponse:
    """Serve the interactive Formula E Pit-Wall Driver Performance Dashboard."""
    initial_payload = TelemetryRequest(
        driver_id=driver_id,
        lap_number=lap_number,
        turn_3_regen_kw=turn_3_regen_kw,
        turn_13_regen_kw=turn_13_regen_kw,
        lift_and_coast_m=lift_and_coast_m,
    )
    evaluation = evaluate_driver_telemetry(initial_payload)
    chart_buf = generate_telemetry_chart_buffer(
        turn_3_regen_kw=turn_3_regen_kw,
        turn_13_regen_kw=turn_13_regen_kw,
        lift_and_coast_m=lift_and_coast_m,
        driver_id=driver_id,
        lap_number=lap_number,
    )
    chart_base64 = base64.b64encode(chart_buf.getvalue()).decode("utf-8")

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "request": request,
            "telemetry": initial_payload,
            "evaluation": evaluation,
            "chart_base64": chart_base64,
        },
    )
