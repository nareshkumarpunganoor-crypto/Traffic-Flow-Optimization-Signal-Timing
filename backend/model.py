"""
Traffic Flow Prediction & Signal Optimization Model.

Two models:
  1. Traffic volume predictor  - predicts next 24h volume
  2. Signal timing optimizer   - recommends green light durations
"""

import os
import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble      import GradientBoostingRegressor, RandomForestClassifier
from sklearn.multioutput   import MultiOutputRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline      import Pipeline
from sklearn.metrics       import mean_absolute_error, mean_squared_error

PRED_LEN = 24
HISTORY  = 24

# Features used
FEATURES = [
    "hour", "day_of_week", "month", "is_weekend",
    "weather_code",
    "vol_north", "vol_south", "vol_east", "vol_west",
    "total_volume", "congestion", "avg_speed_kmh", "incident",
]

# Targets: predict next 24h total volume + green times
TARGETS = [
    "total_volume",
    "green_north", "green_south", "green_east", "green_west",
]


def _make_features(df):
    rows = []
    vals = df[FEATURES].values
    tot  = df["total_volume"].values

    for i in range(HISTORY, len(df) - PRED_LEN):
        r = df.iloc[i]

        # Cyclical encodings
        h_sin = np.sin(2 * np.pi * r["hour"]        / 24)
        h_cos = np.cos(2 * np.pi * r["hour"]        / 24)
        d_sin = np.sin(2 * np.pi * r["day_of_week"] / 7)
        d_cos = np.cos(2 * np.pi * r["day_of_week"] / 7)
        m_sin = np.sin(2 * np.pi * r["month"]       / 12)
        m_cos = np.cos(2 * np.pi * r["month"]       / 12)

        # Lag features (past 24h volume)
        lags = tot[i - HISTORY : i]

        row = np.concatenate([
            [h_sin, h_cos, d_sin, d_cos, m_sin, m_cos,
             r["is_weekend"], r["weather_code"],
             r["vol_north"], r["vol_south"],
             r["vol_east"],  r["vol_west"],
             r["congestion"], r["avg_speed_kmh"],
             r["incident"]],
            lags
        ])
        rows.append(row)

    return np.array(rows, dtype=np.float32)


def _make_targets(df):
    tgts = []
    for i in range(HISTORY, len(df) - PRED_LEN):
        future = df.iloc[i : i + PRED_LEN]
        # Use mean of next 24h for each target
        tgts.append([
            future["total_volume"].mean(),
            future["green_north"].mean(),
            future["green_south"].mean(),
            future["green_east"].mean(),
            future["green_west"].mean(),
        ])
    return np.array(tgts, dtype=np.float32)


class TrafficModel:

    def __init__(self):
        self.pipeline   = None
        self.is_trained = False

    def build(self):
        base = GradientBoostingRegressor(
            n_estimators  = 100,
            max_depth     = 4,
            learning_rate = 0.1,
            subsample     = 0.8,
            random_state  = 42,
        )
        self.pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("model",  MultiOutputRegressor(base, n_jobs=-1)),
        ])
        print("Traffic model pipeline ready.")

    def train(self, df):
        print("Building features...")
        X = _make_features(df)
        y = _make_targets(df)

        split    = int(len(X) * 0.85)
        X_tr, X_val = X[:split], X[split:]
        y_tr, y_val = y[:split], y[split:]

        print(f"Train: {len(X_tr)} | Val: {len(X_val)}")
        print("Fitting... (~20-40 seconds)")

        self.pipeline.fit(X_tr, y_tr)

        y_pred = self.pipeline.predict(X_val)
        mae    = mean_absolute_error(y_val[:, 0], y_pred[:, 0])
        rmse   = np.sqrt(mean_squared_error(y_val[:, 0], y_pred[:, 0]))

        print(f"MAE={mae:.1f} vehicles  RMSE={rmse:.1f} vehicles")
        self.is_trained = True
        return {"mae": round(mae, 1), "rmse": round(rmse, 1)}

    def predict(self, df):
        try:
            # Need at least HISTORY+1 rows
            if len(df) < HISTORY + 1:
                raise ValueError("Not enough data.")

            tail = df.tail(HISTORY + 2).reset_index(drop=True)
            X    = _make_features(tail)

            if len(X) == 0:
                # Build features manually from last row
                row  = df.iloc[-1]
                h_sin = np.sin(2 * np.pi * row["hour"]        / 24)
                h_cos = np.cos(2 * np.pi * row["hour"]        / 24)
                d_sin = np.sin(2 * np.pi * row["day_of_week"] / 7)
                d_cos = np.cos(2 * np.pi * row["day_of_week"] / 7)
                m_sin = np.sin(2 * np.pi * row["month"]       / 12)
                m_cos = np.cos(2 * np.pi * row["month"]       / 12)
                lags  = df["total_volume"].values[-HISTORY:]
                X     = np.concatenate([
                    [h_sin, h_cos, d_sin, d_cos, m_sin, m_cos,
                     row["is_weekend"], row["weather_code"],
                     row["vol_north"], row["vol_south"],
                     row["vol_east"],  row["vol_west"],
                     row["congestion"], row["avg_speed_kmh"],
                     row["incident"]],
                    lags
                ]).reshape(1, -1).astype(np.float32)

            pred = self.pipeline.predict(X[-1:] if len(X) > 1 else X)[0]

            return {
                "total_volume": max(0, int(pred[0])),
                "green_north" : int(np.clip(pred[1], 20, 90)),
                "green_south" : int(np.clip(pred[2], 20, 90)),
                "green_east"  : int(np.clip(pred[3], 20, 90)),
                "green_west"  : int(np.clip(pred[4], 20, 90)),
            }

        except Exception as e:
            print(f"Predict error: {e}")
            raise

    def save(self, path=None):
        if path is None:
            path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "saved_model", "traffic_model.pkl"
            )
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump(self.pipeline, path)
        print(f"Model saved -> {path}")

    def load(self, path=None):
        if path is None:
            path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "saved_model", "traffic_model.pkl"
            )
        if os.path.exists(path):
            self.pipeline   = joblib.load(path)
            self.is_trained = True
            print(f"Model loaded from {path}")
            return True
        print("No saved model found.")
        return False


if __name__ == "__main__":
    from data import load_data
    df = load_data()
    m  = TrafficModel()
    m.build()
    m.train(df)
    m.save()
    print("Training complete!")