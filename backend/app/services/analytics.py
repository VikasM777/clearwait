import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.models.models import UsageRecord, Machine, BlockedHour, Booking, BookingStatus

HRS = list(range(6, 23)) # 6 to 22 (17 hours)
DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
CLUSTER_NAMES = {
    2: ['Low', 'High'],
    3: ['Low', 'Medium', 'High'],
    4: ['Low', 'Medium', 'Medium-High', 'High'],
    5: ['Very Low', 'Low', 'Medium', 'High', 'Very High']
}
PALETTE = ['#16a34a', '#84cc16', '#eab308', '#f97316', '#dc2626']
PALETTE_IDX = {
    2: [0, 4],
    3: [0, 2, 4],
    4: [0, 2, 3, 4],
    5: [0, 1, 2, 3, 4]
}

def compute_slot_stats(db: Session, from_date=None, to_date=None, dow='all', machine_id='all') -> Dict[str, Any]:
    query = db.query(UsageRecord)
    if from_date:
        query = query.filter(UsageRecord.date >= from_date)
    if to_date:
        query = query.filter(UsageRecord.date <= to_date)
    
    records = query.all()
    
    # In-memory filter for weekday and machine
    filtered_records = []
    distinct_dates = set()
    nd = [0] * 7 # count of unique dates per day-of-week (0=Sun..6=Sat)

    for r in records:
        # SQLite / Postgres date to weekday: Python date.weekday() has Monday=0..Sunday=6
        # The frontend uses JavaScript getDay(): Sunday=0, Monday=1, ..., Saturday=6
        d_obj = r.date
        js_dow = (d_obj.weekday() + 1) % 7
        
        if dow != 'all' and int(dow) != js_dow:
            continue
        distinct_dates.add(d_obj)
        
        if machine_id == 'all' or r.machine_id == machine_id:
            filtered_records.append((d_obj, js_dow, r.hour, r.machine_id))

    for d_obj in distinct_dates:
        js_dow = (d_obj.weekday() + 1) % 7
        nd[js_dow] += 1

    # Aggregate counts per (date, hour)
    cnt = {}
    for d_obj, js_dow, hour, m_id in filtered_records:
        k = f"{d_obj.isoformat()}|{hour}"
        cnt[k] = cnt.get(k, 0) + 1

    # Grid: 7 days x 17 hours
    # Each cell: sum of cycles, max of cycles
    grid = [[{'sum': 0, 'max': 0, 'avg': 0.0} for _ in range(len(HRS))] for _ in range(7)]

    for k, count in cnt.items():
        date_str, h_str = k.split('|')
        h = int(h_str)
        if 6 <= h <= 22:
            d_parts = [int(p) for p in date_str.split('-')]
            import datetime
            d_item = datetime.date(d_parts[0], d_parts[1], d_parts[2])
            js_dow = (d_item.weekday() + 1) % 7
            cell = grid[js_dow][h - 6]
            cell['sum'] += count
            cell['max'] = max(cell['max'], count)

    for i in range(7):
        for cell in grid[i]:
            cell['avg'] = cell['sum'] / nd[i] if nd[i] > 0 else 0.0

    return {
        'records_count': len(filtered_records),
        'dates': sorted([d.isoformat() for d in distinct_dates]),
        'nd': nd,
        'grid': grid
    }

def run_kmeans(db: Session, k: int = 3, machine_id: str = 'all') -> Dict[str, Any]:
    k = max(2, min(5, k))
    stats = compute_slot_stats(db, dow='all', machine_id=machine_id)
    grid = stats['grid']
    
    # Build dataset: one row per (weekday, hour) slot with features [avg, max]
    points = []
    for d in range(7):
        for i, h in enumerate(HRS):
            cell = grid[d][i]
            points.append({
                'd': d,
                'h': h,
                'avg': float(cell['avg']),
                'max': float(cell['max'])
            })

    X_raw = np.array([[p['avg'], p['max']] for p in points])
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_raw)

    # Run KMeans with n_init=10 and random_state=42
    kmeans_model = KMeans(n_clusters=k, n_init=10, random_state=42)
    labels = kmeans_model.fit_predict(X_scaled)
    inertia = float(kmeans_model.inertia_)

    # Calculate centroids in original units
    centroids_data = []
    for c_id in range(k):
        mask = (labels == c_id)
        cluster_points = [points[idx] for idx, is_in in enumerate(mask) if is_in]
        count = len(cluster_points)
        avg_cycles = float(np.mean([p['avg'] for p in cluster_points])) if count > 0 else 0.0
        max_cycles = float(np.mean([p['max'] for p in cluster_points])) if count > 0 else 0.0
        centroids_data.append({
            'c': c_id,
            'n': count,
            'avg': round(avg_cycles, 2),
            'max': round(max_cycles, 2)
        })

    # Sort cluster centroids by average usage (lowest = Low, middle = Medium, highest = High)
    centroids_sorted = sorted(centroids_data, key=lambda x: x['avg'])
    names = CLUSTER_NAMES.get(k, CLUSTER_NAMES[3])
    palette_indices = PALETTE_IDX.get(k, PALETTE_IDX[3])

    c_mapping = {}
    for rank, cent in enumerate(centroids_sorted):
        cent['rank'] = rank
        cent['name'] = names[rank]
        cent['color'] = PALETTE[palette_indices[rank]]
        c_mapping[cent['c']] = cent

    # Attach labels, colors, and rank to points
    slots_result = []
    for idx, p in enumerate(points):
        assigned_cluster = labels[idx]
        cent_meta = c_mapping[assigned_cluster]
        slots_result.append({
            'd': p['d'],
            'h': p['h'],
            'avg': round(p['avg'], 2),
            'max': round(p['max'], 2),
            'rank': cent_meta['rank'],
            'name': cent_meta['name'],
            'color': cent_meta['color']
        })

    return {
        'k': k,
        'inertia': round(inertia, 2),
        'total_cycles': stats['records_count'],
        'total_days': len(stats['dates']),
        'cents': [c for c in centroids_sorted if c['n'] > 0],
        'slots': slots_result
    }
