# WEC-IMSA-Pace-Analyser

Overview

The WEC/IMSA Pace Analyser is a Python Streamlit application designed to analyse lap times and performance data from endurance racing events (WEC, IMSA). It helps you quickly evaluate average lap times, top speeds, and driver performance across selected cars, manufacturers, or individual drivers.

Features

- Class Selection: analyse only a chosen car class.
- Car Selection: Focus on specific cars within the class.
- Time Filter: Restrict analysis to laps within a specific race time window.
- Top % Laps: Compute averages using only the fastest portion of laps.
- Maximum Delta: Ignore laps that are too far from the fastest lap.
- Individual Driver Performance: Break down averages by driver.
- Manufacturer Average: Compute averages grouped by manufacturer.
- Team & Top Speed: Shows team names and average top speed alongside lap times.
- Driver(s) Column: Displays driver names if analysing individual performance; otherwise shows "All".

Important Notes

    Approximation Only: The app provides averages based on the available lap data, but it does not capture all race variables. Factors like car damage, pit strategy, traffic, weather, and setup changes can heavily influence pace but are not reflected in the data.

    CSV Format: Input CSV must contain the following columns:
    NUMBER, LAP_TIME, CLASS, CROSSING_FINISH_LINE_IN_PIT, MANUFACTURER, ELAPSED, DRIVER_NAME, TEAM, TOP_SPEED

    Laps in Pit: Laps crossing the finish line while in the pit are ignored in calculations.

## Usage

- **Upload a CSV file.** Here's how to get the correct files:
  - **IMSA:**
    1. Go to [https://imsa.results.alkamelcloud.com/](https://imsa.results.alkamelcloud.com/)
    2. Select a Season/Event and then select the RACE folder.
    3. Choose the last hour of the race.
    4. Download the Time Cards CSV.
  - **WEC:**
    1. Go to [https://fiawec.alkamelsystems.com/](https://fiawec.alkamelsystems.com/)
    2. Navigate to the Event and then select the RACE folder.
    3. Choose the last hour.
    4. Download the Analysis Hour XX CSV file.
  - **Practice Sessions:**  
    The app can also process CSVs from practice or qualifying sessions, as long as they follow the same column format. Simply upload the CSV from the session you want to analyse.

- **Select Class and Cars:** Choose the car class and the cars you want to analyse.
- **Adjust Filters:** Set the time window, top percentage of laps, and maximum delta if needed.
- **Choose Averages:** Check boxes for Manufacturer Average or Individual Driver Performance.
- **View Results:** The table displays:
  - Driver(s)
  - Car
  - Team
  - Manufacturer
  - Average Lap Time
  - Laps Used
  - Average Top Speed
  
Disclaimer: This app should not be used to accurately assess car or driver performance. There are numerous variables in a race that are not reflected in the dataset, such as damage, strategy, weather and so on. It's important to watch the races or read detailed reports to understand the full context behind the results.
