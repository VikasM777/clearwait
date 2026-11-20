from datetime import datetime, date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.models.models import Machine, MachineStatus, Booking, BookingStatus, UsageRecord, BlockedHour
from app.schemas.schemas import DashboardStats, AnalyticsSummary, KMeansResponse, RecommendationResponse, RecommendationSlot
from app.services.analytics import compute_slot_stats, run_kmeans, HRS, DAYS

router = APIRouter(prefix="", tags=["Analytics & Recommendations"])

@router.get("/dashboard/stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    now = datetime.now()
    today = now.date()
    current_hour = now.hour
    js_dow = (today.weekday() + 1) % 7

    machines = db.query(Machine).all()
    total_machines = len(machines)
    active_machines = [m for m in machines if m.status != MachineStatus.MAINTENANCE]

    # Occupied now: machine with status='occupied' or confirmed booking today at current hour
    confirmed_now = {
        b.machine_id for b in db.query(Booking.machine_id).filter(
            Booking.date == today,
            Booking.hour == current_hour,
            Booking.status == BookingStatus.CONFIRMED
        ).all()
    }
    occupied_now_count = sum(
        1 for m in active_machines if m.status == MachineStatus.OCCUPIED or m.id in confirmed_now
    )
    available_now_count = max(0, len(active_machines) - occupied_now_count)

    confirmed_bookings_count = db.query(Booking).filter(Booking.status == BookingStatus.CONFIRMED).count()
    total_wash_cycles = db.query(UsageRecord).count()

    # Unique dates
    distinct_dates_count = db.query(func.count(func.distinct(UsageRecord.date))).scalar() or 1
    denom = distinct_dates_count * (total_machines or 1) * len(HRS)
    avg_utilisation = (total_wash_cycles / denom * 100.0) if denom > 0 else 0.0

    # KMeans clustering (k=3) for demand
    km_data = run_kmeans(db, k=3, machine_id="all")
    current_slot = next((s for s in km_data['slots'] if s['d'] == js_dow and s['h'] == current_hour), None)
    
    current_demand_level = f"{current_slot['name']} demand" if current_slot else "Closed"
    current_demand_color = current_slot['color'] if current_slot else "var(--mut)"

    # Today's strip
    today_demand_strip = []
    for h in HRS:
        s = next((slot for slot in km_data['slots'] if slot['d'] == js_dow and slot['h'] == h), None)
        today_demand_strip.append({
            "hour": h,
            "label": f"{h:02d}:00",
            "name": s['name'] if s else "Low",
            "color": s['color'] if s else "#16a34a",
            "avg": s['avg'] if s else 0.0,
            "is_current": (h == current_hour)
        })

    # Recommended times today (quick top 3 slots)
    blocked_hours = {b.hour for b in db.query(BlockedHour.hour).all()}
    candidate_slots = []
    for h in HRS:
        if h <= current_hour or h in blocked_hours:
            continue
        s = next((slot for slot in km_data['slots'] if slot['d'] == js_dow and slot['h'] == h), None)
        if not s:
            continue
        # Free machines in that slot
        booked_in_slot = {
            b.machine_id for b in db.query(Booking.machine_id).filter(
                Booking.date == today,
                Booking.hour == h,
                Booking.status == BookingStatus.CONFIRMED
            ).all()
        }
        free_cnt = sum(1 for m in active_machines if m.id not in booked_in_slot)
        candidate_slots.append({
            "hour": h,
            "time": f"{h:02d}:00",
            "cluster_name": s['name'],
            "cluster_color": s['color'],
            "avg": s['avg'],
            "free_machines": free_cnt
        })

    candidate_slots.sort(key=lambda x: (x['avg'], -x['free_machines']))
    recommended_today = candidate_slots[:3]

    return DashboardStats(
        total_machines=total_machines,
        occupied_now=occupied_now_count,
        available_now=available_now_count,
        confirmed_bookings=confirmed_bookings_count,
        total_wash_cycles=total_wash_cycles,
        average_utilisation=round(avg_utilisation, 1),
        current_demand_level=current_demand_level,
        current_demand_color=current_demand_color,
        today_demand_strip=today_demand_strip,
        recommended_today=recommended_today
    )

@router.get("/analytics", response_model=AnalyticsSummary)
def get_analytics(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    dow: str = "all",
    machine_id: str = "all",
    db: Session = Depends(get_db)
):
    stats = compute_slot_stats(db, from_date=from_date, to_date=to_date, dow=dow, machine_id=machine_id)
    nd_total = len(stats['dates']) or 1

    # Hourly average across the queried dataset
    # Total cycles per hour / total days
    query = db.query(UsageRecord)
    if from_date:
        query = query.filter(UsageRecord.date >= from_date)
    if to_date:
        query = query.filter(UsageRecord.date <= to_date)
    all_recs = query.all()

    # Filter by machine and dow
    filtered_recs = []
    for r in all_recs:
        js_dow = (r.date.weekday() + 1) % 7
        if dow != "all" and int(dow) != js_dow:
            continue
        if machine_id != "all" and r.machine_id != machine_id:
            continue
        filtered_recs.append(r)

    # Hourly avg
    hour_counts = {h: 0 for h in HRS}
    daily_counts = {}
    weekday_cnt = 0
    weekend_cnt = 0
    machine_counts = {}

    for r in filtered_recs:
        h = r.hour
        if h in hour_counts:
            hour_counts[h] += 1
        d_str = r.date.isoformat()
        daily_counts[d_str] = daily_counts.get(d_str, 0) + 1
        
        js_dow = (r.date.weekday() + 1) % 7
        if js_dow in (0, 6):
            weekend_cnt += 1
        else:
            weekday_cnt += 1

        machine_counts[r.machine_id] = machine_counts.get(r.machine_id, 0) + 1

    hourly_avg = [round(hour_counts[h] / nd_total, 2) for h in HRS]

    # Daily trend sorted by date
    all_dates_sorted = sorted(stats['dates'])
    daily_trend = {
        "labels": all_dates_sorted,
        "data": [daily_counts.get(d, 0) for d in all_dates_sorted]
    }

    # Weekday vs weekend
    weekday_vs_weekend = {
        "labels": ["Weekday", "Weekend"],
        "data": [weekday_cnt, weekend_cnt]
    }

    # Machine-wise utilisation
    all_machines = db.query(Machine).order_by(Machine.id).all()
    denom = nd_total * len(HRS)
    machine_utilisation = []
    for m in all_machines:
        m_recs = machine_counts.get(m.id, 0)
        pct = round((m_recs / denom * 100.0), 1) if denom > 0 else 0.0
        machine_utilisation.append({
            "machine_id": m.id,
            "machine_name": m.name,
            "count": m_recs,
            "utilisation_pct": pct
        })

    # Peak hours and low-demand slots
    hour_metrics = [{"hour": h, "avg": hourly_avg[i]} for i, h in enumerate(HRS)]
    sorted_by_avg = sorted(hour_metrics, key=lambda x: x['avg'], reverse=True)
    peak_hours = sorted_by_avg[:5]
    low_demand = list(reversed(sorted_by_avg[-5:]))

    # Booking trends
    bookings = db.query(Booking).all()
    booking_counts_by_date = {}
    for b in bookings:
        d_str = b.date.isoformat()
        booking_counts_by_date[d_str] = booking_counts_by_date.get(d_str, 0) + 1
    
    b_dates = sorted(booking_counts_by_date.keys())
    booking_trends = {
        "labels": b_dates,
        "data": [booking_counts_by_date[d] for d in b_dates]
    }

    # Heatmap 7 x 17
    max_avg = 1.0
    for row in stats['grid']:
        for cell in row:
            if cell['avg'] > max_avg:
                max_avg = cell['avg']

    heatmap = {
        "hours": HRS,
        "days": DAYS,
        "max_avg": round(max_avg, 2),
        "grid": stats['grid']
    }

    return AnalyticsSummary(
        dates=stats['dates'],
        total_cycles=len(filtered_recs),
        hourly_avg=hourly_avg,
        daily_trend=daily_trend,
        weekday_vs_weekend=weekday_vs_weekend,
        machine_utilisation=machine_utilisation,
        peak_hours=peak_hours,
        low_demand_slots=low_demand,
        booking_trends=booking_trends,
        heatmap=heatmap
    )

@router.get("/kmeans", response_model=KMeansResponse)
def get_kmeans(
    k: int = Query(3, ge=2, le=5),
    machine_id: str = Query("all"),
    db: Session = Depends(get_db)
):
    return run_kmeans(db, k=k, machine_id=machine_id)

@router.get("/recommend", response_model=RecommendationResponse)
def get_recommendations(
    date_val: date = Query(..., alias="date"),
    period: str = Query("Morning"), # Morning, Afternoon, Evening
    machine_id: str = Query("any", alias="machine"),
    db: Session = Depends(get_db)
):
    period_ranges = {
        "Morning": (6, 11),
        "Afternoon": (12, 16),
        "Evening": (17, 22)
    }
    start_h, end_h = period_ranges.get(period, (6, 22))

    now = datetime.now()
    is_today = (date_val == now.date())
    cur_hour = now.hour
    js_dow = (date_val.weekday() + 1) % 7

    # Run clustering
    km_data = run_kmeans(db, k=3, machine_id="all")
    machines = db.query(Machine).all()
    total_machines_count = len(machines) or 1
    active_machines = [m for m in machines if m.status != MachineStatus.MAINTENANCE]

    blocked_hours = {b.hour for b in db.query(BlockedHour.hour).all()}

    # Confirmed bookings on that day
    confirmed_bookings = db.query(Booking).filter(
        Booking.date == date_val,
        Booking.status == BookingStatus.CONFIRMED
    ).all()
    booking_map = {}
    for b in confirmed_bookings:
        booking_map.setdefault(b.hour, set()).add(b.machine_id)

    recommendations: List[RecommendationSlot] = []

    for h in range(start_h, end_h + 1):
        if h in blocked_hours:
            continue
        if is_today and h <= cur_hour:
            continue
        
        slot_cluster = next((s for s in km_data['slots'] if s['d'] == js_dow and s['h'] == h), None)
        if not slot_cluster:
            continue

        booked_machine_ids = booking_map.get(h, set())
        free_active = [m for m in active_machines if m.id not in booked_machine_ids]

        if machine_id != "any":
            free_for_req = [m for m in free_active if m.id == machine_id]
        else:
            free_for_req = free_active

        expected_pct = min(100.0, (slot_cluster['avg'] / total_machines_count) * 100.0)

        # Plain language explanation
        if slot_cluster['rank'] == 0:
            reason = f"Usually only {slot_cluster['avg']:.1f} of {total_machines_count} machines run at {h:02d}:00 on {DAYS[js_dow]}s – a quiet, low-usage slot."
        elif slot_cluster['name'] == 'High':
            reason = f"Peak hour: about {slot_cluster['avg']:.1f} machines run at once on {DAYS[js_dow]}s. Expect a queue."
        else:
            reason = f"Moderate demand (about {slot_cluster['avg']:.1f} machines busy on {DAYS[js_dow]}s)."

        recommendations.append(RecommendationSlot(
            hour=h,
            label=f"{h:02d}:00 – {h+1:02d}:00",
            cluster_name=slot_cluster['name'],
            cluster_color=slot_cluster['color'],
            cluster_rank=slot_cluster['rank'],
            expected_demand_pct=round(expected_pct, 1),
            free_machines_count=len(free_for_req),
            free_machine_ids=[m.id for m in free_for_req],
            reason=reason
        ))

    # Rank recommendations from least to most crowded (lowest avg first, then most free machines)
    recommendations.sort(key=lambda x: (x.expected_demand_pct, -x.free_machines_count))

    # Highest cluster rank for peak hours to avoid
    max_rank = max(c['rank'] for c in km_data['cents']) if km_data['cents'] else 2
    peak_hours_to_avoid = [
        s['h'] for s in km_data['slots'] if s['d'] == js_dow and s['rank'] == max_rank
    ]

    return RecommendationResponse(
        date=date_val.isoformat(),
        period=period,
        machine=machine_id,
        recommendations=recommendations,
        peak_hours_to_avoid=peak_hours_to_avoid
    )
