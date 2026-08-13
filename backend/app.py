"""
Flask API - Traffic Flow Optimization
"""

import os
import sys
import traceback
import numpy as np
from datetime import datetime, timedelta
from flask      import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

BACKEND_DIR  = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR     = os.path.dirname(BACKEND_DIR)
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")
MODEL_FILE   = os.path.join(BACKEND_DIR, "saved_model", "traffic_model.pkl")
DATA_FILE    = os.path.join(BACKEND_DIR, "data", "traffic.csv")

sys.path.insert(0, BACKEND_DIR)

from data  import load_data, generate_data
from model import TrafficModel

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)

# Generate data if missing
if not os.path.exists(DATA_FILE):
    print("Generating traffic data...")
    generate_data(days=365)

df = load_data()

# Load model
tm = TrafficModel()
tm.build()
MODEL_READY = tm.load(MODEL_FILE)

# Auto train if no model
if not MODEL_READY:
    print("Auto training model...")
    try:
        metrics     = tm.train(df)
        tm.save(MODEL_FILE)
        MODEL_READY = True
        print(f"Auto trained: MAE={metrics['mae']}")
    except Exception as e:
        print(f"Auto train failed: {e}")
        MODEL_READY = False


# ── Static files ───────────────────────────
@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.route("/<path:fn>")
def static_files(fn):
    return send_from_directory(FRONTEND_DIR, fn)


# ── Helpers ────────────────────────────────
def get_congestion_level(volume):
    if   volume < 500:  return "Low",    "green"
    elif volume < 1000: return "Medium", "yellow"
    elif volume < 1500: return "High",   "orange"
    else:               return "Severe", "red"

def mock_prediction():
    hour = datetime.now().hour
    if   7  <= hour <= 9:  base = 900
    elif 17 <= hour <= 19: base = 1000
    elif 0  <= hour <= 5:  base = 80
    else:                  base = 400

    vol = int(base + np.random.normal(0, 80))
    return {
        "total_volume": max(0, vol),
        "green_north" : int(np.clip(20 + vol / 15, 20, 90)),
        "green_south" : int(np.clip(20 + vol / 16, 20, 90)),
        "green_east"  : int(np.clip(20 + vol / 14, 20, 90)),
        "green_west"  : int(np.clip(20 + vol / 17, 20, 90)),
    }


# ── API Routes ─────────────────────────────

@app.route("/api/status")
def api_status():
    return jsonify({
        "status"     : "ok",
        "model_ready": MODEL_READY,
        "data_rows"  : len(df),
        "python"     : sys.version.split()[0],
        "time"       : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })


@app.route("/api/train")
def api_train():
    global MODEL_READY, df
    try:
        print("Training started...")
        df      = load_data()
        metrics = tm.train(df)
        tm.save(MODEL_FILE)
        MODEL_READY = True
        return jsonify({
            "success": True,
            "message": "Model trained! MAE=" + str(metrics["mae"]) + " vehicles",
            "metrics": metrics,
        })
    except Exception as e:
        err = traceback.format_exc()
        print("TRAIN ERROR:", err)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/predict")
def api_predict():
    global MODEL_READY
    try:
        if MODEL_READY:
            try:
                pred         = tm.predict(df)
                level, color = get_congestion_level(pred["total_volume"])
                congestion   = round(min(1.0, pred["total_volume"] / 4000), 3)
                avg_speed    = round(max(5, 60 * (1 - congestion * 0.8)), 1)
                result       = {
                    "total_volume"    : pred["total_volume"],
                    "congestion"      : congestion,
                    "congestion_level": level,
                    "congestion_color": color,
                    "avg_speed_kmh"   : avg_speed,
                    "signal_timing"   : {
                        "north": pred["green_north"],
                        "south": pred["green_south"],
                        "east" : pred["green_east"],
                        "west" : pred["green_west"],
                    },
                }
            except Exception as e:
                print(f"Model predict failed: {e} - using mock")
                result = mock_prediction()
        else:
            result = mock_prediction()

        return jsonify({
            "success"   : True,
            "model_used": MODEL_READY,
            "prediction": result,
        })

    except Exception as e:
        print("PREDICT ERROR:", traceback.format_exc())
        return jsonify({
            "success"   : True,
            "model_used": False,
            "prediction": mock_prediction(),
        })

@app.route("/api/forecast")
def api_forecast():
    try:
        now    = datetime.now()
        result = []

        for i in range(24):
            ft   = now + timedelta(hours=i + 1)
            hour = ft.hour
            wd   = ft.weekday()

            if   7  <= hour <= 9:  base = 900
            elif 17 <= hour <= 19: base = 1000
            elif 0  <= hour <= 5:  base = 80
            elif 12 <= hour <= 13: base = 600
            else:                  base = 400

            weekend = 0.6 if wd >= 5 else 1.0
            vol     = max(0, int(base * weekend + np.random.normal(0, 60)))

            level, color = get_congestion_level(vol)
            congestion   = round(min(1.0, vol / 4000), 3)

            result.append({
                "hour"            : hour,
                "label"           : ft.strftime("%H:00"),
                "volume"          : vol,
                "congestion"      : congestion,
                "congestion_level": level,
                "congestion_color": color,
                "avg_speed"       : round(max(5, 60 * (1 - congestion * 0.8)), 1),
                "green_time"      : int(np.clip(20 + vol / 15, 20, 90)),
            })

        return jsonify({"success": True, "forecast": result})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/history")
def api_history():
    try:
        hours  = int(request.args.get("hours", 48))
        recent = df.tail(hours)

        records = []
        for _, row in recent.iterrows():
            records.append({
                "timestamp"   : str(row["timestamp"]),
                "hour"        : int(row["hour"]),
                "volume"      : int(row["total_volume"]),
                "congestion"  : float(row["congestion"]),
                "avg_speed"   : float(row["avg_speed_kmh"]),
                "weather"     : str(row["weather"]),
                "incident"    : int(row["incident"]),
                "green_north" : int(row["green_north"]),
                "green_south" : int(row["green_south"]),
                "green_east"  : int(row["green_east"]),
                "green_west"  : int(row["green_west"]),
            })

        return jsonify({"success": True, "data": records})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/stats")
def api_stats():
    try:
        days   = int(request.args.get("days", 30))
        recent = df.tail(days * 24)
        grp    = recent.groupby("hour")["total_volume"].mean()

        return jsonify({
            "success": True,
            "stats": {
                "avg_daily_volume" : round(float(recent["total_volume"].sum() / days), 0),
                "avg_hourly_volume": round(float(recent["total_volume"].mean()), 0),
                "max_volume"       : int(recent["total_volume"].max()),
                "min_volume"       : int(recent["total_volume"].min()),
                "avg_speed"        : round(float(recent["avg_speed_kmh"].mean()), 1),
                "avg_congestion"   : round(float(recent["congestion"].mean()), 3),
                "incident_count"   : int(recent["incident"].sum()),
                "peak_hour"        : int(grp.idxmax()),
                "low_hour"         : int(grp.idxmin()),
                "hourly_pattern"   : {
                    int(k): round(float(v), 0)
                    for k, v in grp.items()
                },
                "weather_breakdown": {
                    "clear"     : int((recent["weather"] == "clear").sum()),
                    "rain"      : int((recent["weather"] == "rain").sum()),
                    "heavy_rain": int((recent["weather"] == "heavy_rain").sum()),
                },
            },
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/optimize", methods=["POST"])
def api_optimize():
    """
    Optimize signal timing for given traffic volumes.
    Body: { north, south, east, west, weather_code }
    """
    try:
        data    = request.get_json() or {}
        north   = int(data.get("north",   400))
        south   = int(data.get("south",   400))
        east    = int(data.get("east",    400))
        west    = int(data.get("west",    400))
        weather = int(data.get("weather", 0))

        total      = north + south + east + west
        cycle_time = 120  # total cycle in seconds

        # Proportional green time allocation
        def green_time(vol):
            return int(np.clip(20 + (vol / max(total, 1)) * 80, 20, 90))

        n_green = green_time(north)
        s_green = green_time(south)
        e_green = green_time(east)
        w_green = green_time(west)

        congestion = round(min(1.0, total / 4000), 3)
        level, color = get_congestion_level(total)

        # Recommendations
        recs = []
        max_vol = max(north, south, east, west)
        if max_vol == north:
            recs.append("Prioritize North-South green phase")
        if max_vol == east:
            recs.append("Prioritize East-West green phase")
        if weather == 2:
            recs.append("Heavy rain detected - reduce speed limits")
        if congestion > 0.7:
            recs.append("High congestion - activate alternate routes")
        if total > 3000:
            recs.append("Enable adaptive signal control mode")
        if congestion < 0.3:
            recs.append("Low traffic - extend pedestrian crossing time")

        return jsonify({
            "success": True,
            "optimized": {
                "signal_timing": {
                    "north": n_green,
                    "south": s_green,
                    "east" : e_green,
                    "west" : w_green,
                },
                "total_volume"    : total,
                "congestion"      : congestion,
                "congestion_level": level,
                "congestion_color": color,
                "cycle_time"      : cycle_time,
                "recommendations" : recs,
            },
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── Main ───────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting on port {port}")
    app.run(debug=False, host="0.0.0.0", port=port)