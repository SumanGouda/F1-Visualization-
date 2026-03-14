import arcade
import sqlite3
import shutil 
import time
import os
import warnings
warnings.filterwarnings("ignore")
import pandas as pd
from rendering.ui_renderer import draw_leaderboard, draw_lap_number, draw_corners, draw_weather_card
from core.data_exporter import DataExporter, get_max_session_rows 
from core.session_manager import SessionManager
from core.telemetry_processor import TelemetryProcessor
from utils.helpers import prepare_track_layout, get_screen_coords, calculate_weather_frame_ratio

# Layout Constants
SCREEN_WIDTH = 1500
SCREEN_HEIGHT = 900
SCREEN_TITLE = "F1 Race Replay - Arcade Edition"

# Configuration
year = 2025
GP_NAME = "bahrain"  
DB_ROOT = f"database/race_{GP_NAME}"

def hex_to_rgb(hex_str):
    if not hex_str or not isinstance(hex_str, str): return (128, 128, 128)
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

class F1ReplayWindow(arcade.Window):
    def __init__(self):
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
        arcade.set_background_color(arcade.color.BLACK)

        # Game State
        self.driver_metadata = {}  # Loaded from results.db
        self.sorted_drivers = []   # For the leaderboard
        self.track_points = []
        self.corner_data = []
        self.session_time = 0.0   
        self.speed_multiplier = 1  
        
        self.is_paused = False
        
        self.current_race_time = pd.Timedelta(seconds=0)
        
        # This will hold the weather snapshot for on_draw
        self.current_weather = None
        
        self.setup()

    def setup(self):
        # Load the F1 Session
        self.manager = SessionManager(year=year, gp=GP_NAME.title(), session_type="R")
        
        if self.manager.session is None:
            print("Failed to load F1 Session.")
            return

        # Create the Disk Source (The .db files) 
        self.exporter = DataExporter(self.manager)
        self.exporter.export_all_data()
        self.db_path = f"database/race_{self.manager.gp.lower()}"
        
        # Prepare UI Metadata & Layout 
        self.results_df = self.manager.get_session_results()
        if self.results_df is not None:
            self.results_df = self.results_df.sort_values(by='GridPosition', na_position='last')
            self.driver_metadata = self.results_df.set_index('Abbreviation').to_dict('index')
            self.sorted_drivers = list(self.driver_metadata.keys())
        
        self.rotation = self.manager.get_circuit_rotation() or 0

        # Generate the Racing Line (Track Map) and corner
        self.corner_data = self.manager.get_corner_data()
        fastest_lap = self.manager.get_session_fastest_lap()
        if fastest_lap is not None:
            tp_track = TelemetryProcessor(fastest_lap)
            raw_x, raw_y = tp_track.get_track_coordinates()
            if raw_x is not None and raw_y is not None:
                layout = prepare_track_layout(
                    raw_x, raw_y, SCREEN_WIDTH, SCREEN_HEIGHT, 
                    padding_left=320, rotation=self.rotation
                )
                (self.track_points, self.offset_x, self.offset_y, self.track_scale) = layout
            
        # Pre-calculate Colors for Performance 
        self.car_colors = {abbr: hex_to_rgb(info.get('TeamColor', '#FFFFFF')) 
                           for abbr, info in self.driver_metadata.items()}

        # Linear Timing Initialization 
        self.is_paused = False      
        self.current_car_positions = {abbr: (0, 0) for abbr in self.driver_metadata.keys()}
        self.driver_row_counters = {abbr: 0 for abbr in self.driver_metadata.keys()}
        
        # 7. Frame & Weather Timing Logic 
        self.max_rows = get_max_session_rows(self.driver_metadata.keys(), self.db_path)
        self.weather_frame_ratio = calculate_weather_frame_ratio(self.driver_metadata.keys(), self.db_path)

        # 8. Master Counters
        self.global_frame_counter = 0
        self.weather_index = 0
        self.current_weather = None
        
        print(f"Setup complete. Weather ratio set to 1:{self.weather_frame_ratio}")
        
    def on_update(self, delta_time):
        if self.is_paused:
            return

        # 1. Weather Update Logic
        # We trigger if it's the very first frame (0) OR the ratio is hit
        if self.global_frame_counter % self.weather_frame_ratio == 0:
            weather_db_path = os.path.join(self.db_path, "weather.db")
            
            if os.path.exists(weather_db_path):
                try:
                    conn = sqlite3.connect(weather_db_path)
                    conn.row_factory = sqlite3.Row 
                    cursor = conn.cursor()
                    
                    # LIMIT 1 OFFSET ? pulls the exact row for the current weather index
                    query = "SELECT * FROM weather LIMIT 1 OFFSET ?"
                    cursor.execute(query, (self.weather_index,))
                    result = cursor.fetchone()
                    conn.close()

                    if result:
                        self.current_weather = result
                        self.weather_index += 1
                except Exception as e:
                    print(f"Weather Update Error: {e}")

        # 2. Advance the Master Frame Counter
        # We increment AFTER the weather check so frame 0 is handled first
        self.global_frame_counter += 1

        race_positions = []

        # 3. Query each driver's database (Car Updates)
        for abbr in self.driver_metadata.keys():
            db_path = os.path.join(self.db_path, f"{abbr}.db")
            if not os.path.exists(db_path): 
                continue

            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Each car moves one row per frame
                current_row_index = self.driver_row_counters[abbr]
                
                query = """
                    SELECT x, y, total_distance, gap_ahead, speed, rpm, ngear, 
                           throttle, brake, drs, lap_number 
                    FROM telemetry LIMIT 1 OFFSET ?
                """
                cursor.execute(query, (current_row_index,))
                result = cursor.fetchone()
                conn.close()

                if result:
                    (x, y, dist, gap, speed, rpm, gear, throttle, brake, drs, lap) = result
                    
                    # Update map positions using coordinate conversion
                    if pd.notna(x) and pd.notna(y):
                        self.current_car_positions[abbr] = (x, y)
                    
                    # Update metadata for card-style UI
                    self.driver_metadata[abbr].update({
                        'total_distance': dist,
                        'gap_ahead': gap if gap is not None else 0.0,
                        'speed': speed, 'rpm': rpm, 'gear': gear,
                        'throttle': throttle, 'brake': brake, 'drs': drs, 'lap_number': lap
                    })
            
                    if dist is not None and pd.notna(dist):
                        race_positions.append((abbr, dist))
                    
                    # Move this specific driver to their next data row
                    self.driver_row_counters[abbr] += 1
                    
            except Exception as e:
                print(f"Update error for {abbr}: {e}")

        # 4. Re-sort Leaderboard based on total distance covered
        if race_positions:
            race_positions.sort(key=lambda x: x[1], reverse=True)
            self.sorted_drivers = [d[0] for d in race_positions]
                           
    def on_draw(self):
        self.clear()
        
        # 1. Draw Track Layout
        if self.track_points:
            arcade.draw_line_strip(self.track_points, (255, 255, 255, 200), 8)
            arcade.draw_line_strip(self.track_points, arcade.color.BLACK, 4)
        
        # 2. Draw Corners
        if self.corner_data:
            try:
                draw_corners(self.corner_data, self.rotation, self.track_scale, self.offset_x, self.offset_y)
            except Exception as e:
                print(f"Skipping corner draw due to error: {e}")
                
        # 3. Draw Driver Circles (The "Cars")
        for abbr in self.sorted_drivers:
            pos = self.current_car_positions.get(abbr)
            if pos is None or pos == (0, 0):
                continue

            fx, fy = get_screen_coords(
                pos[0], pos[1],
                self.rotation, self.track_scale, self.offset_x, self.offset_y
            )
            color = self.car_colors.get(abbr, arcade.color.GRAY)
            arcade.draw_circle_filled(fx, fy, 8, color)
            arcade.draw_text(abbr, fx + 12, fy, arcade.color.WHITE, 10, bold=True, anchor_y="center")
        
        # 4. Draw Primary UI Elements
        draw_leaderboard(self.sorted_drivers, self.driver_metadata, self.car_colors, self.height)
        
        try:
            total_laps = int(self.results_df['Laps'].max()) if self.results_df is not None else 0
        except (ValueError, TypeError):
            total_laps = 0
        draw_lap_number(self.sorted_drivers, self.driver_metadata, self.width, self.height, int(total_laps))
        
        # 5. Draw Weather Card (Last Layer) 
        if self.current_weather is not None:
            draw_weather_card(self.current_weather, self.width, self.height)
            
def main(delete_on_exit=True):
    """
    Main entry point for the F1 Replay Visualizer.
    :param delete_on_exit: If True, wipes .db files upon closing.  
    """
    window = None
    try: 
        window = F1ReplayWindow()
        arcade.run()
    except Exception as e: 
        print(f"An unexpected error occurred: {e}")
    finally: 
        if delete_on_exit and window and hasattr(window, 'exporter'):
            print("Cleaning up database files before exit as requested...")  
        else:
            print("Persistence mode: Database files preserved for next run.")  

if __name__ == "__main__": 
    main(delete_on_exit=False)

