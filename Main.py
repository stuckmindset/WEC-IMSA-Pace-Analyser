import streamlit as st
import pandas as pd
import re

# -----------------------------
# App title
# -----------------------------
st.title("WEC/IMSA Pace Analyzer")

# -----------------------------
# File upload
# -----------------------------
uploaded_file = st.file_uploader("Upload CSV file", type="csv")

if uploaded_file is not None:
    # Load CSV
    df = pd.read_csv(uploaded_file, sep=';', engine='python', header=0, dtype=str)
    df.columns = [c.strip() for c in df.columns]

    # Check required columns
    required_cols = ["NUMBER", "LAP_TIME", "CLASS", "CROSSING_FINISH_LINE_IN_PIT", 
                     "MANUFACTURER", "ELAPSED", "DRIVER_NAME", "TEAM", "TOP_SPEED"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        st.error(f"Missing required column(s): {', '.join(missing_cols)}")
    else:
        df = df[required_cols]

        # -----------------------------
        # Parse lap times
        # -----------------------------
        time_re = re.compile(r"(\d+):(\d{2}\.\d+)")
        def parse_time_to_seconds(t):
            if pd.isna(t) or t == '':
                return None
            m = time_re.search(str(t).strip())
            if not m:
                return None
            return int(m.group(1)) * 60 + float(m.group(2))
        df["lap_seconds"] = df["LAP_TIME"].apply(parse_time_to_seconds)

        # -----------------------------
        # Parse ELAPSED into fractional hours
        # -----------------------------
        elapsed_re = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2}\.\d+)")
        def parse_elapsed_to_hours(t):
            if pd.isna(t) or t == '':
                return None
            m = elapsed_re.search(str(t).strip())
            if not m:
                return None
            hours = int(m.group(1)) if m.group(1) else 0
            minutes = int(m.group(2))
            seconds = float(m.group(3))
            return hours + (minutes / 60) + (seconds / 3600)
        df["elapsed_hours"] = df["ELAPSED"].apply(parse_elapsed_to_hours)

        # -----------------------------
        # Ensure TOP_SPEED is numeric
        # -----------------------------
        df["TOP_SPEED"] = pd.to_numeric(df["TOP_SPEED"], errors='coerce')

        # -----------------------------
        # Class selection
        # -----------------------------
        available_classes = df["CLASS"].dropna().unique()
        target_class = st.selectbox("Select car class", options=available_classes)

        # -----------------------------
        # Cars selection (multi-select in expander)
        # -----------------------------
        cars_in_class = df[df["CLASS"].str.upper() == str(target_class).upper()]["NUMBER"].dropna().unique()
        cars_in_class_sorted = sorted(cars_in_class, key=lambda x: int(re.sub(r"\D", "", x)))

        with st.expander("Cars (select which to include)"):
            selected_cars = st.multiselect(
                "Select Cars",
                options=cars_in_class_sorted,
                default=cars_in_class_sorted
            )

        # Filter df to only selected cars
        df = df[df["NUMBER"].isin(selected_cars)]

        # -----------------------------
        # Top % Laps slider
        # -----------------------------
        target_percent = st.slider("Top % Laps", 0.1, 0.8, 0.6, 0.05)

        # -----------------------------
        # Hour range slider
        # -----------------------------
        min_hour = df["elapsed_hours"].min()
        max_hour = df["elapsed_hours"].max()
        hour_range = st.slider("Race Time Window",
                               min_value=float(min_hour),
                               max_value=float(max_hour),
                               value=(float(min_hour), float(max_hour)),
                               step=0.01,
                               format="%.0f")

        # Filter laps by selected hours
        df = df[(df["elapsed_hours"] >= hour_range[0]) & (df["elapsed_hours"] <= hour_range[1])]

        # -----------------------------
        # Best lap threshold input
        # -----------------------------
        max_delta = st.number_input(
            "Laptime Range",
            value=0, 
            help="This defines the maximum allowed delta in laptime from the fastest lap. Laps outside this range will be ignored."
        )
        if max_delta == 0:
            max_delta = None

        # -----------------------------
        # Toggle for averages
        # -----------------------------
        avg_by_manufacturer = st.checkbox("Manufacturer Average")
        avg_by_driver = st.checkbox("Individual Driver Performance")  # NEW

        # -----------------------------
        # Automatic calculation (no button)
        # -----------------------------
        df["CLASS_clean"] = df["CLASS"].astype(str).str.upper().str.strip()
        mask_class = df["CLASS_clean"] == str(target_class).upper()
        mask_no_pit = ~(df["CROSSING_FINISH_LINE_IN_PIT"].astype(str).str.upper().str.strip() == "B")
        df_class = df[mask_class & mask_no_pit].copy()

        results = []

        if avg_by_driver:
            # Process per driver
            unique_drivers = df_class["DRIVER_NAME"].dropna().unique()
            for driver in unique_drivers:
                subset = df_class[df_class["DRIVER_NAME"] == driver].dropna(subset=["lap_seconds", "TOP_SPEED"])
                if len(subset) == 0:
                    results.append({"Driver(s)": driver, "Car": "N/A", "Team": "N/A", "Manufacturer": "N/A",
                                    "Average": "N/A", "Laps Used": 0, "Average Top Speed": "N/A"})
                    continue

                car = subset["NUMBER"].iloc[0]
                team = subset["TEAM"].iloc[0]
                manufacturer = subset["MANUFACTURER"].iloc[0]

                if max_delta is not None:
                    best_lap = subset["lap_seconds"].min()
                    subset = subset[subset["lap_seconds"] <= best_lap + max_delta]
                if len(subset) == 0:
                    results.append({"Driver(s)": driver, "Car": car, "Team": team, "Manufacturer": manufacturer,
                                    "Average": f"N/A (> {max_delta}s)", "Laps Used": 0, "Average Top Speed": "N/A"})
                    continue

                sorted_times = subset["lap_seconds"].sort_values().to_list()
                cutoff = max(1, int(len(sorted_times) * target_percent))
                best_times_idx = subset["lap_seconds"].sort_values().index[:cutoff]

                best_times = subset.loc[best_times_idx, "lap_seconds"].to_list()
                avg = sum(best_times) / len(best_times)
                avg_str = f"{int(avg // 60)}:{avg % 60:06.3f}"

                avg_top_speed = subset.loc[best_times_idx, "TOP_SPEED"].mean()
                avg_top_speed_str = f"{avg_top_speed:.1f}" if not pd.isna(avg_top_speed) else "N/A"

                results.append({"Driver(s)": driver, "Car": car, "Team": team, "Manufacturer": manufacturer,
                                "Average": avg_str, "Laps Used": len(best_times), "Average Top Speed": avg_top_speed_str})

        elif avg_by_manufacturer:
            # Process per manufacturer
            unique_mfrs = df_class["MANUFACTURER"].dropna().unique()
            for mfr in unique_mfrs:
                subset = df_class[df_class["MANUFACTURER"] == mfr].dropna(subset=["lap_seconds", "TOP_SPEED"])
                if len(subset) == 0:
                    results.append({"Driver(s)": "All", "Car": "N/A", "Team": "N/A", "Manufacturer": mfr,
                                    "Average": "N/A", "Laps Used": 0, "Average Top Speed": "N/A"})
                    continue

                if max_delta is not None:
                    best_lap = subset["lap_seconds"].min()
                    subset = subset[subset["lap_seconds"] <= best_lap + max_delta]
                if len(subset) == 0:
                    results.append({"Driver(s)": "All", "Car": "N/A", "Team": "N/A", "Manufacturer": mfr,
                                    "Average": f"N/A (> {max_delta}s)", "Laps Used": 0, "Average Top Speed": "N/A"})
                    continue

                sorted_times = subset["lap_seconds"].sort_values().to_list()
                cutoff = max(1, int(len(sorted_times) * target_percent))
                best_times_idx = subset["lap_seconds"].sort_values().index[:cutoff]

                best_times = subset.loc[best_times_idx, "lap_seconds"].to_list()
                avg = sum(best_times) / len(best_times)
                avg_str = f"{int(avg // 60)}:{avg % 60:06.3f}"

                avg_top_speed = subset.loc[best_times_idx, "TOP_SPEED"].mean()
                avg_top_speed_str = f"{avg_top_speed:.1f}" if not pd.isna(avg_top_speed) else "N/A"

                results.append({"Driver(s)": "All", "Car": "Multiple", "Team": "Multiple", "Manufacturer": mfr,
                                "Average": avg_str, "Laps Used": len(best_times), "Average Top Speed": avg_top_speed_str})

        else:
            # Process per car
            unique_cars = sorted(df_class["NUMBER"].dropna().unique(), key=lambda x: int(re.sub(r"\D", "", x)))
            for car in unique_cars:
                subset = df_class[df_class["NUMBER"] == car].dropna(subset=["lap_seconds", "TOP_SPEED"])
                if len(subset) == 0:
                    results.append({"Driver(s)": "All", "Car": car, "Team": "N/A", "Manufacturer": "N/A",
                                    "Average": "N/A", "Laps Used": 0, "Average Top Speed": "N/A"})
                    continue

                team = subset["TEAM"].iloc[0]
                manufacturer = subset["MANUFACTURER"].iloc[0]

                if max_delta is not None:
                    best_lap = subset["lap_seconds"].min()
                    subset = subset[subset["lap_seconds"] <= best_lap + max_delta]
                if len(subset) == 0:
                    results.append({"Driver(s)": "All", "Car": car, "Team": team, "Manufacturer": manufacturer,
                                    "Average": f"N/A (> {max_delta}s)", "Laps Used": 0, "Average Top Speed": "N/A"})
                    continue

                sorted_times = subset["lap_seconds"].sort_values().to_list()
                cutoff = max(1, int(len(sorted_times) * target_percent))
                best_times_idx = subset["lap_seconds"].sort_values().index[:cutoff]

                best_times = subset.loc[best_times_idx, "lap_seconds"].to_list()
                avg = sum(best_times) / len(best_times)
                avg_str = f"{int(avg // 60)}:{avg % 60:06.3f}"

                avg_top_speed = subset.loc[best_times_idx, "TOP_SPEED"].mean()
                avg_top_speed_str = f"{avg_top_speed:.1f}" if not pd.isna(avg_top_speed) else "N/A"

                results.append({"Driver(s)": "All", "Car": car, "Team": team, "Manufacturer": manufacturer,
                                "Average": avg_str, "Laps Used": len(best_times), "Average Top Speed": avg_top_speed_str})

        # Show results as table
        st.table(pd.DataFrame(results)[[""Car", "Team", "Manufacturer", "Driver(s)", "Average", "Laps Used", "Average Top Speed"]])                               