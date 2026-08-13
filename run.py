import os
import sys

BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)


def main():
    print("=" * 40)
    print("  Traffic Flow Optimization")
    print("=" * 40)

    # Generate data
    data_path = os.path.join(BACKEND, "data", "traffic.csv")
    if not os.path.exists(data_path):
        print("\n[1/2] Generating traffic data...")
        from data import generate_data
        generate_data(days=365)
    else:
        print("\n[1/2] Data exists - skipping.")

    # Import app
    from app import app, tm, MODEL_READY

    # Train if needed
    if not MODEL_READY:
        ans = input("\nNo model found. Train now? (y/n): ").strip().lower()
        if ans == "y":
            from data import load_data
            df = load_data()
            tm.train(df)
            tm.save()
            print("Model saved!")

    print("\n[2/2] Starting server...")
    print("      Open http://localhost:5000")
    print("      Press Ctrl+C to stop\n")
    print("=" * 40)

    app.run(debug=False, host="0.0.0.0", port=5000)


if __name__ == "__main__":
    main()