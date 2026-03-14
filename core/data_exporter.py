import sqlite3
import os
import shutil  
import time    
import gc
import pandas as pd
from core.telemetry_processor import TelemetryProcessor
from core.session_manager import SessionManager 

class DataExporter:
    def __init__(self, session_manager):
        self.sm = session_manager  
        self.gp = self.sm.gp.lower()
        self.base_path = f"database/race_{self.gp}" 
        
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path)

    def _export_driver_race(self, driver_abbr):
        db_path = os.path.join(self.base_path, f"{driver_abbr}.db")
        
        # Check if the file exists before doing ANY heavy lifting 
        if os.path.exists(db_path):
            print(f"Skipping {driver_abbr}: Database already exists.")
            return # Exit immediately to save time 
        
        driver_laps = self.sm.get_driver_laps(driver_abbr)
        if driver_laps is None:
            return 

        conn = sqlite3.connect(db_path)
        
        # Clear old data to start fresh [cite: 2026-01-20]
        conn.execute('DROP TABLE IF EXISTS telemetry')
        conn.execute('''
            CREATE TABLE telemetry (
                session_time REAL PRIMARY KEY,
                x REAL, y REAL, speed INTEGER,
                rpm INTEGER, ngear INTEGER, 
                throttle INTEGER, brake BOOLEAN,
                drs INTEGER, gap_ahead REAL,
                total_distance REAL, lap_number INTEGER
            )
        ''')

        # This list will hold dataframes for every lap 
        all_laps_data = []
        cumulative_distance = 0.0

        for _, lap in driver_laps.iterrows():
            # IMPORTANT: Explicitly get telemetry for this specific lap 
            try:
                tel = lap.get_telemetry() 
                if tel.empty:
                    continue
                
                # Create the dataframe for this specific lap  
                lap_df = pd.DataFrame({
                    'session_time': tel['Time'].dt.total_seconds(),
                    'x': tel['X'],
                    'y': tel['Y'],
                    'speed': tel['Speed'],
                    'rpm': tel['RPM'],
                    'ngear': tel['nGear'],       
                    'throttle': tel['Throttle'],
                    'brake': tel['Brake'],
                    'drs': tel['DRS'],          
                    'gap_ahead': tel.get('DistanceToDriverAhead', 0), 
                    'total_distance': tel['Distance'] + cumulative_distance,
                    'lap_number': int(lap['LapNumber'])
                })
                all_laps_data.append(lap_df)
                
                # Update distance for the start of the next lap  
                cumulative_distance += tel['Distance'].iloc[-1]
            except Exception as e:
                print(f"Skipping lap {lap['LapNumber']} for {driver_abbr}: {e}")

        # Combine all laps and save once for better performance  
        if all_laps_data:
            final_df = pd.concat(all_laps_data).drop_duplicates(subset=['session_time'])
            final_df.to_sql('telemetry', conn, if_exists='append', index=False)

        conn.execute("CREATE INDEX idx_time ON telemetry(session_time)")
        conn.commit()
        conn.close()
           
    def cleanup(self):
        gc.collect() 
        time.sleep(0.7) 
        if os.path.exists(self.base_path):
            try:
                shutil.rmtree(self.base_path)
                print(f"Successfully cleaned up: {self.base_path}")
            except PermissionError:
                 print(f"Warning: {self.base_path} is still locked. Cleanup skipped.")
    
    def _export_weather(self):
        """Exports session weather data to a dedicated database file."""
        db_path = os.path.join(self.base_path, "weather.db")
        
        if os.path.exists(db_path):
            print("Skipping Weather: Database already exists.")
            return

        weather_data = self.sm.get_weather_data()
        if weather_data is None or weather_data.empty:
            print("No weather data found to export.")
            return

        conn = sqlite3.connect(db_path)
        
        # Ensure we start fresh with the cleaned feature [cite: 2026-01-20]
        conn.execute('DROP TABLE IF EXISTS weather')
        
        # Cleaning: Convert Timedelta to total seconds for easier SQL math
        weather_df = weather_data.copy()
        weather_df['Time'] = weather_df['Time'].dt.total_seconds()

        # Save to SQL
        weather_df.to_sql('weather', conn, if_exists='replace', index=False)
        
        # Create an index on Time for faster lookups later
        conn.execute("CREATE INDEX idx_weather_time ON weather(Time)")
        
        conn.commit()
        conn.close()
        print(f"Weather export complete: {db_path}")

    def export_all_data(self):
        results = self.sm.get_session_results()
        if results is None or results.empty:
            print("No session results found. Cannot export data.")
            return

        driver_list = results['Abbreviation'].tolist()
        print(f"Starting sequential export for {len(driver_list)} drivers...")
   
        for abbr in driver_list:
            try:
                print(f"Processing Driver: {abbr}...")
                self._export_driver_race(abbr)
            except Exception as e:
                print(f"Failed export for {abbr}: {e}")

        try:
            print("Processing: Weather...")
            self._export_weather()
        except Exception as e:
            print(f"Failed to export weather data: {e}")

        print("Export complete! All databases (Drivers & Weather) are ready.")       

# Helper Functions
              
def get_max_session_rows(driver_abbrs, db_root):
    max_rows = 0
    
    for abbr in driver_abbrs:
        db_path = os.path.join(db_root, f"{abbr}.db")
        if not os.path.exists(db_path):
            continue
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # SQL COUNT is nearly instantaneous compared to len(dataframe)
        cursor.execute("SELECT COUNT(*) FROM telemetry")
        count = cursor.fetchone()[0]
        
        if count > max_rows:
            max_rows = count
            
        conn.close()
    
    return max_rows