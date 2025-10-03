import streamlit as st
import pandas as pd
import re

st.title("WEC/IMSA Pace Analyser")

uploaded_file = st.file_uploader("Upload CSV file", type="csv")

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, sep=';', engine='python', header=0, dtype=str)
    df.columns = [c.strip() for c in df.columns]

    required_cols = ["NUMBER", "LAP_TIME", "CLASS", "MANUFACTURER", "ELAPSED",
                     "DRIVER_NAME", "TEAM", "TOP_SPEED", "CROSSING_FINISH_LINE_IN_PIT"]
    missing_cols = [c for c in required_cols if c not in df.columns]

    if missing_cols:
        st.error(f"Missing required column(s): {', '.join(missing_cols)}")
    else:
        df = df[required_cols]

        # -----------------------------
        # Parse lap times into seconds
        # supports M:SS.sss and H:MM:SS.sss
        # -----------------------------
        lap_time_re = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{2}\.\d+)$")

        def parse_time_to_seconds(t):
            """
            Accepts:
              - "2:08.976"         -> minutes:seconds.millis
              - "2:00:07.559"      -> hours:minutes:seconds.millis
            Returns seconds as float, or None if unparsable/empty.
            """
            if pd.isna(t) or str(t).strip() == "":
                return None
            s = str(t).strip()
            m = lap_time_re.match(s)
            if m:
                hours = int(m.group(1)) if m.group(1) else 0
                minutes = int(m.group(2))
                seconds = float(m.group(3))
                return hours * 3600 + minutes * 60 + seconds
            # fallback: try to parse a simple float (seconds)
            try:
                return float(s)
            except Exception:
                return None

        df["lap_seconds"] = df["LAP_TIME"].apply(parse_time_to_seconds)

        # -----------------------------
        # Parse ELAPSED into fractional hours
        # -----------------------------
        elapsed_re = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2}\.\d+)")
        def parse_elapsed_to_hours(t):
            if pd.isna(t) or str(t).strip() == '':
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
        # Ensure TOP_SPEED is numeric, missing/empty values become NaN
        # -----------------------------
        df["TOP_SPEED"] = pd.to_numeric(df["TOP_SPEED"], errors='coerce')

        # -----------------------------
        # Class selection
        # -----------------------------
        available_classes = df["CLASS"].dropna().unique()
        target_class = st.selectbox("Select car class", options=available_classes)

        # -----------------------------
        # Cars selection
        # -----------------------------
        cars_in_class = df[df["CLASS"].str.upper() == str(target_class).upper()]["NUMBER"].dropna().unique()
        cars_in_class_sorted = sorted(cars_in_class, key=lambda x: int(re.sub(r"\D", "", x)))

        with st.expander("Cars"):
            selected_cars = st.multiselect(
                "Select Cars",
                options=cars_in_class_sorted,
                default=cars_in_class_sorted,
                help="Here you can exclude cars from the analysis."
            )

        df = df[df["NUMBER"].isin(selected_cars)]

        # -----------------------------
        # Top % laps slider
        # -----------------------------
        target_percent = st.slider(
            "Top % laps", 0.1, 0.7, 0.6, 0.05,
            help="Lower values will filter only the fastest laps. Higher values show a more representative stint average."
        )

        # -----------------------------
        # Time window slider
        # -----------------------------
        min_hour = df["elapsed_hours"].min()
        max_hour = df["elapsed_hours"].max()
        hour_range = st.slider(
            "Session time window(h)",
            min_value=float(min_hour),
            max_value=float(max_hour),
            value=(float(min_hour), float(max_hour)),
            step=0.01,
            format="%.0f",
            help="Restrict the analysis to a certain portion of the session."
        )
        df = df[(df["elapsed_hours"] >= hour_range[0]) & (df["elapsed_hours"] <= hour_range[1])]

        # -----------------------------
        # Percentage-based laptime filters
        # -----------------------------
        manuf_delta = st.slider(
            "Manufacturer laptime filter (% of class best)",
            min_value=101, max_value=120, value=110,
            help="Laps must be within this % of the class' fastest lap."
        )

        driver_delta = st.slider(
            "Driver laptime filter (% of driver's best)",
            min_value=101, max_value=120, value=105,
            help="Laps must be within this % of the driver's fastest lap."
        )

        avg_by_manufacturer = st.checkbox("Manufacturer average")
        avg_by_driver = st.checkbox("Individual driver performance")

        # -----------------------------
        # Clean class and filter invalid/pit/first laps
        # CROSSING_FINISH_LINE_IN_PIT: empty -> normal lap, 'B' -> in pit
        # Exclude rows where CROSSING_FINISH_LINE_IN_PIT == 'B'
        # Also exclude rows with no valid lap_seconds or lap_seconds <= 0 (first lap/invalid)
        # -----------------------------
        df["CLASS_clean"] = df["CLASS"].astype(str).str.upper().str.strip()
        mask_class = df["CLASS_clean"] == str(target_class).upper()
        df_class = df[mask_class].copy()

        # Exclude pit laps marked with 'B' and keep only normal-type laps (empty or NaN)
        df_class = df_class[df_class["CROSSING_FINISH_LINE_IN_PIT"].astype(str).str.strip().ne("B")]

        # Keep only rows with valid lap_seconds > 0
        df_class = df_class[df_class["lap_seconds"].notna()]
        df_class = df_class[df_class["lap_seconds"] > 1]

        results = []

        def process_subset(subset, entity_name, car_name, team_name, manufacturer_name, delta_pct, ref="driver"):
            if len(subset) == 0:
                return {
                    "Driver(s)": entity_name,
                    "Car": car_name,
                    "Team": team_name,
                    "Manufacturer": manufacturer_name,
                    "Average Lap Time": "N/A",
                    "Valid Laps": 0,
                    "Average Top Speed": "N/A"
                }

            # reference best depends on whether we're using class best or subset best
            if ref == "class":
                # class fastest lap across df_class (already filtered)
                ref_best = df_class["lap_seconds"].min()
            else:
                ref_best = subset["lap_seconds"].min()

            cutoff_val = ref_best * (delta_pct / 100.0)
            subset = subset[subset["lap_seconds"] <= cutoff_val]

            if len(subset) == 0:
                return {
                    "Driver(s)": entity_name,
                    "Car": car_name,
                    "Team": team_name,
                    "Manufacturer": manufacturer_name,
                    "Average Lap Time": f"N/A (> {delta_pct}%)",
                    "Valid Laps": 0,
                    "Average Top Speed": "N/A"
                }

            sorted_times = subset["lap_seconds"].sort_values().to_list()
            cutoff = max(1, int(len(sorted_times) * target_percent))
            best_times_idx = subset["lap_seconds"].sort_values().index[:cutoff]
            best_times = subset.loc[best_times_idx, "lap_seconds"].to_list()
            avg = sum(best_times) / len(best_times)
            avg_str = f"{int(avg // 60)}:{avg % 60:06.3f}"
            avg_top_speed = subset.loc[best_times_idx, "TOP_SPEED"].mean()
            avg_top_speed_str = f"{avg_top_speed:.1f}" if not pd.isna(avg_top_speed) else "N/A"

            return {
                "Driver(s)": entity_name,
                "Car": car_name,
                "Team": team_name,
                "Manufacturer": manufacturer_name,
                "Average Lap Time": avg_str,
                "Valid Laps": len(best_times),
                "Average Top Speed": avg_top_speed_str
            }

        # -----------------------------
        # Build results depending on mode
        # -----------------------------
        if avg_by_driver:
            for driver in df_class["DRIVER_NAME"].dropna().unique():
                subset = df_class[df_class["DRIVER_NAME"] == driver]
                if len(subset) == 0:
                    continue
                car = subset["NUMBER"].iloc[0]
                team = subset["TEAM"].iloc[0]
                manufacturer = subset["MANUFACTURER"].iloc[0]
                results.append(process_subset(subset, driver, car, team, manufacturer, driver_delta, ref="driver"))

        elif avg_by_manufacturer:
            for mfr in df_class["MANUFACTURER"].dropna().unique():
                subset = df_class[df_class["MANUFACTURER"] == mfr]
                if len(subset) == 0:
                    continue
                results.append(process_subset(subset, "All", "Multiple", "Multiple", mfr, manuf_delta, ref="class"))

        else:
            for car in sorted(df_class["NUMBER"].dropna().unique(), key=lambda x: int(re.sub(r"\D", "", x))):
                subset = df_class[df_class["NUMBER"] == car]
                if len(subset) == 0:
                    continue
                team = subset["TEAM"].iloc[0]
                manufacturer = subset["MANUFACTURER"].iloc[0]
                results.append(process_subset(subset, "All", car, team, manufacturer, manuf_delta, ref="class"))

        # -----------------------------
        # Display
        # -----------------------------
        styled_df = pd.DataFrame(results)[[
            "Car", "Team", "Manufacturer", "Driver(s)", "Average Lap Time", "Valid Laps", "Average Top Speed"
        ]].reset_index(drop=True)

        st.dataframe(
            styled_df.style.set_table_styles(
                [
                    {"selector": "th.col0", "props": [("min-width", "60px")]},
                    {"selector": "th.col1", "props": [("min-width", "200px")]},
                    {"selector": "th.col2", "props": [("min-width", "120px")]},
                    {"selector": "th.col3", "props": [("min-width", "200px")]},
                ]
            ),
            use_container_width=True
        )

        st.markdown("---")
        st.markdown(
            """
            **Disclaimer**:  
            *This app should not be used to accurately assess car or driver performance.  
            There are numerous variables in a race that are not reflected in the dataset,  
            such as damage, strategy, weather and so on. It's important to watch the races  
            or read detailed reports to understand the full context behind the results.*
            """,
            unsafe_allow_html=True
        )

