import streamlit as st
import pandas as pd
import re

st.title("WEC/IMSA Pace Analyser")

uploaded_file = st.file_uploader("Upload CSV file", type="csv")

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, sep=';', engine='python', header=0, dtype=str)
    df.columns = [c.strip() for c in df.columns]

    required_cols = [
        "NUMBER", "LAP_TIME", "CLASS", "MANUFACTURER", "ELAPSED",
        "DRIVER_NAME", "TEAM", "TOP_SPEED", "LAP_NUMBER", "CROSSING_FINISH_LINE_IN_PIT"
    ]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        st.error(f"Missing required column(s): {', '.join(missing_cols)}")
    else:
        # Only keep needed cols
        df = df[required_cols]

        # Parse laptime to seconds
        time_re = re.compile(r"(\d+):(\d{2}\.\d+)")
        def parse_time_to_seconds(t):
            if pd.isna(t) or t == '':
                return None
            m = time_re.search(str(t).strip())
            if not m:
                return None
            return int(m.group(1)) * 60 + float(m.group(2))

        df["lap_seconds"] = df["LAP_TIME"].apply(parse_time_to_seconds)

        # Parse elapsed to hours
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

        # Cast to numeric where needed
        df["TOP_SPEED"] = pd.to_numeric(df["TOP_SPEED"], errors='coerce')
        df["LAP_NUMBER"] = pd.to_numeric(df["LAP_NUMBER"], errors='coerce')

        # Drop pit in/out laps and first lap
        df = df[(df["CROSSING_FINISH_LINE_IN_PIT"] != "B") & (df["LAP_NUMBER"] > 1)]

        # Select class
        available_classes = df["CLASS"].dropna().unique()
        target_class = st.selectbox("Select car class", options=available_classes)

        # Select cars
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

        # Filtering sliders
        class_sec = st.slider(
            "Class lap window (s)",
            min_value=1, max_value=10, value=10,
            help="Laps must be within this many seconds of the class fastest lap."
        )
        driver_sec = st.slider(
            "Driver lap window (s)",
            min_value=1, max_value=10, value=5,
            help="In driver analysis, laps must also be within this many seconds of the driver's fastest lap."
        )
        target_percent = st.slider(
            "Percent of best laps to average",
            min_value=10, max_value=100, value=60, step=5,
            help="Average will be based on the fastest X% of valid laps."
        )

        # Session time filter
        min_hour = df["elapsed_hours"].min()
        max_hour = df["elapsed_hours"].max()
        hour_range = st.slider(
            "Session time window (h)",
            min_value=float(min_hour),
            max_value=float(max_hour),
            value=(float(min_hour), float(max_hour)),
            step=0.01,
            format="%.0f",
            help="Restrict the analysis to a certain portion of the session."
        )
        df = df[(df["elapsed_hours"] >= hour_range[0]) & (df["elapsed_hours"] <= hour_range[1])]

        # Checkboxes
        avg_by_manufacturer = st.checkbox("Manufacturer average")
        avg_by_driver = st.checkbox("Individual driver performance")

        # Normalise class
        df["CLASS_clean"] = df["CLASS"].astype(str).str.upper().str.strip()
        mask_class = df["CLASS_clean"] == str(target_class).upper()
        df_class = df[mask_class].copy()

        # Find class fastest lap
        class_best = df_class["lap_seconds"].min()

        results = []

        def process_subset(subset, entity_name, car_name, team_name, manufacturer_name, class_best, driver_best=None):
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

            # Step 1: class filter
            subset = subset[subset["lap_seconds"] <= class_best + class_sec]

            # Step 2: driver filter if enabled
            if driver_best is not None:
                subset = subset[subset["lap_seconds"] <= driver_best + driver_sec]

            if len(subset) == 0:
                return {
                    "Driver(s)": entity_name,
                    "Car": car_name,
                    "Team": team_name,
                    "Manufacturer": manufacturer_name,
                    "Average Lap Time": "N/A (filtered)",
                    "Valid Laps": 0,
                    "Average Top Speed": "N/A"
                }

            # Step 3: fastest X% of laps
            sorted_times = subset["lap_seconds"].sort_values().to_list()
            cutoff = max(1, int(len(sorted_times) * (target_percent/100.0)))
            best_times = sorted_times[:cutoff]

            avg = sum(best_times) / len(best_times)
            avg_str = f"{int(avg // 60)}:{avg % 60:06.3f}"

            avg_top_speed = subset.loc[subset["lap_seconds"].isin(best_times), "TOP_SPEED"].mean()
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

        if avg_by_driver:
            for driver in df_class["DRIVER_NAME"].dropna().unique():
                subset = df_class[df_class["DRIVER_NAME"] == driver]
                if len(subset) == 0:
                    continue
                car = subset["NUMBER"].iloc[0]
                team = subset["TEAM"].iloc[0]
                manufacturer = subset["MANUFACTURER"].iloc[0]
                driver_best = subset["lap_seconds"].min()
                results.append(process_subset(subset, driver, car, team, manufacturer, class_best, driver_best))
        elif avg_by_manufacturer:
            for mfr in df_class["MANUFACTURER"].dropna().unique():
                subset = df_class[df_class["MANUFACTURER"] == mfr]
                if len(subset) == 0:
                    continue
                results.append(process_subset(subset, "All", "Multiple", "Multiple", mfr, class_best))
        else:
            for car in sorted(df_class["NUMBER"].dropna().unique(), key=lambda x: int(re.sub(r"\D", "", x))):
                subset = df_class[df_class["NUMBER"] == car]
                if len(subset) == 0:
                    continue
                team = subset["TEAM"].iloc[0]
                manufacturer = subset["MANUFACTURER"].iloc[0]
                results.append(process_subset(subset, "All", car, team, manufacturer, class_best))

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
            <div style="color: gray; font-size: 12px; margin-top: 30px;">
            <b>Disclaimer:</b> This app should not be used to accurately assess car or driver performance.  
            There are numerous variables in a race that are not reflected in the dataset,  
            such as damage, strategy, weather and so on. It's important to watch the races  
            or read detailed reports to understand the full context behind the results.
            </div>
            """,
            unsafe_allow_html=True
        )
