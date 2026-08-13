"""
Generate synthetic traffic flow data.
Simulates realistic traffic patterns for
4 intersections with hourly data.
"""

import numpy as np
import pandas as pd
import os


def generate_data(days=365):
    np.random.seed(42)
    hours      = days * 24
    timestamps = pd.date_range(start="2023-01-01", periods=hours, freq="h")

    rows = []
    for ts in timestamps:
        h  = ts.hour
        wd = ts.weekday()
        m  = ts.month

        # Base traffic volume by hour
        if   7  <= h <= 9:   base = 900   # morning rush
        elif 12 <= h <= 13:  base = 600   # lunch
        elif 17 <= h <= 19:  base = 1000  # evening rush
        elif 0  <= h <= 5:   base = 80    # night
        else:                base = 400   # normal

        # Weekend reduction
        weekend = 0.6 if wd >= 5 else 1.0

        # Season effect
        season = 1 + 0.1 * np.sin(2 * np.pi * (m - 3) / 12)

        # Weather effect (random)
        weather_code = np.random.choice([0, 1, 2], p=[0.6, 0.3, 0.1])
        weather_factor = {0: 1.0, 1: 0.85, 2: 0.65}[weather_code]
        weather_names  = {0: "clear", 1: "rain", 2: "heavy_rain"}

        # Traffic volume for 4 intersections
        vol = {}
        for inter in ["N", "S", "E", "W"]:
            noise = np.random.normal(0, 50)
            inter_factor = {"N": 1.0, "S": 0.9, "E": 1.1, "W": 0.85}[inter]
            vol[inter] = max(0, int(
                base * weekend * season * weather_factor * inter_factor + noise
            ))

        total_volume = sum(vol.values())

        # Optimal green time (seconds) based on volume
        # Range: 20-90 seconds
        def optimal_green(v):
            return int(np.clip(20 + (v / 1000) * 70, 20, 90))

        # Congestion level 0-1
        congestion = min(1.0, total_volume / 4000)

        # Average speed (km/h) inversely related to congestion
        avg_speed = max(5, 60 * (1 - congestion * 0.8))

        # Incident probability
        incident = 1 if np.random.random() < 0.03 else 0

        rows.append({
            "timestamp"       : ts,
            "hour"            : h,
            "day_of_week"     : wd,
            "month"           : m,
            "is_weekend"      : int(wd >= 5),
            "weather_code"    : weather_code,
            "weather"         : weather_names[weather_code],
            "vol_north"       : vol["N"],
            "vol_south"       : vol["S"],
            "vol_east"        : vol["E"],
            "vol_west"        : vol["W"],
            "total_volume"    : total_volume,
            "congestion"      : round(congestion, 3),
            "avg_speed_kmh"   : round(avg_speed, 1),
            "incident"        : incident,
            "green_north"     : optimal_green(vol["N"]),
            "green_south"     : optimal_green(vol["S"]),
            "green_east"      : optimal_green(vol["E"]),
            "green_west"      : optimal_green(vol["W"]),
        })

    df = pd.DataFrame(rows)

    save_dir  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, "traffic.csv")
    df.to_csv(save_path, index=False)
    print(f"Generated {len(df)} records -> {save_path}")
    return df


def load_data():
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "data", "traffic.csv"
    )
    if not os.path.exists(path):
        print("No data found - generating...")
        return generate_data()
    df = pd.read_csv(path, parse_dates=["timestamp"])
    print(f"Loaded {len(df)} records")
    return df


if __name__ == "__main__":
    generate_data(days=365)
    print("Done!")