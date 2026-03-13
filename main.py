import arcade
import sqlite3
import shutil 
import time
import os
import numpy as np
import pandas as pd
from core.data_exporter import DataExporter  
from core.session_manager import SessionManager
from core.telemetry_processor import TelemetryProcessor
from utils.helpers import prepare_track_layout, get_screen_coords

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
        self.session_time = 0.0   
        self.speed_multiplier = 1  
        
        self.is_paused = False
        
        self.setup()

    def setup(self):
        # 1. Load the F1 Session
        self.manager = SessionManager(year=year, gp=GP_NAME.title(), session_type="R")
        
        if self.manager.session is None:
            return

        # 2. Create the Disk Source (The .db files) 
        self.exporter = DataExporter(self.manager)
        self.exporter.export_all_drivers() 

        # 3. Prepare UI Metadata & Layout 
        results_df = self.manager.get_session_results()
        if results_df is not None:
            results_df = results_df.sort_values(by='GridPosition', na_position='last')
            
            # Now convert to dictionary and list to lock in this "starting order" [cite: 2026-03-07]
            self.driver_metadata = results_df.set_index('Abbreviation').to_dict('index')
            self.sorted_drivers = list(self.driver_metadata.keys())
        
        self.rotation = self.manager.get_circuit_rotation() or 0

        # 4. Generate the Racing Line (Track Map) 
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
            
        # 5. Pre-calculate Colors for Performance 
        self.car_colors = {abbr: hex_to_rgb(info.get('TeamColor', '#FFFFFF')) 
                           for abbr, info in self.driver_metadata.items()}

        # 6. Linear Timing Initialization 
        self.is_paused = False      
        self.current_car_positions = {abbr: (0, 0) for abbr in self.driver_metadata.keys()}
        self.driver_row_counters = {abbr: 0 for abbr in self.driver_metadata.keys()}
        
    def on_update(self, delta_time):
        if self.is_paused:
            return

        # 1. Advance the Master Clock 
        self.session_time += delta_time * self.speed_multiplier
        race_positions = []

        # 2. Query each driver's database for their current position 
        for abbr in self.driver_metadata.keys():
            db_path = os.path.join(DB_ROOT, f"{abbr}.db")
            if not os.path.exists(db_path): 
                continue

            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Logic Update: Use OFFSET to pick the next row in sequence 
                # 'LIMIT 1' ensures we only bring one row into RAM.
                # 'OFFSET ?' skips all previous rows to find the current one.
                current_row_index = self.driver_row_counters[abbr]
                
                query = """
                    SELECT x, y, total_distance, gap_ahead, speed, rpm, ngear, throttle, brake, drs, lap_number
                    FROM telemetry 
                    LIMIT 1 OFFSET ?
                """
                cursor.execute(query, (current_row_index,))
                result = cursor.fetchone()
                conn.close()

                if result:
                    # 1. Unpack all features from the database
                    (x, y, dist, gap, speed, rpm, gear, throttle, brake, drs, lap) = result
                    
                    # 2. Update Live Position (for the track map) [cite: 2026-03-07]
                    if pd.notna(x) and pd.notna(y):
                        self.current_car_positions[abbr] = (x, y)
                    else:
                        self.current_car_positions[abbr] = None
                    
                    # 3. Store EVERYTHING in metadata for later use 
                    # We update the dictionary so your 'card-style' UI has access to all stats.
                    self.driver_metadata[abbr].update({
                        'total_distance': dist,
                        'gap_ahead': gap if gap is not None else 0.0,
                        'speed': speed,
                        'rpm': rpm,
                        'gear': gear,
                        'throttle': throttle,
                        'brake': brake,
                        'drs': drs,
                        'lap_number': lap
                    })
            
                # 4. Add to list for the current frame's leaderboard sorting
                if dist is not None and pd.notna(dist):
                    race_positions.append((abbr, dist))
                
                # Increment the row counter to get the next "frame" of data 
                self.driver_row_counters[abbr] += 1
                
            except Exception as e:
                print(f"Update error for {abbr}: {e}")

        # 3. Re-sort the leaderboard based on total distance traveled 
        # This ensures the P1 driver is always at the top of your card UI 
        if race_positions:
            race_positions.sort(key=lambda x: x[1], reverse=True)
            self.sorted_drivers = [d[0] for d in race_positions]
                   
    def on_draw(self):
        self.clear()
        
        # 1. Draw Track Layout
        if self.track_points:
            arcade.draw_line_strip(self.track_points, arcade.color.WHITE, 8)
            
            # 2. Draw the "In-field" (Black line to 'hollow out' the middle) 
            # Making this slightly thinner (e.g., width 4) creates the two-line effect
            arcade.draw_line_strip(self.track_points, arcade.color.BLACK, 4)
            
        # 2. Draw Leaderboard (Left Side Cards) 
        self.draw_leaderboard()
        
        # 3. Draw Driver Circles (The "Cars")
        # Loop through sorted_drivers to maintain layering based on rank 
        for abbr in self.sorted_drivers:
            pos = self.current_car_positions.get(abbr)
            if pos is None or pos == (0, 0):
                continue

            # Convert database meters to screen pixel coordinates  
            fx, fy = get_screen_coords(
                pos[0], pos[1],
                self.rotation, self.track_scale, self.offset_x, self.offset_y
            )
            color = self.car_colors.get(abbr, arcade.color.GRAY)
            arcade.draw_circle_filled(fx, fy, 8, color)
            arcade.draw_circle_outline(fx, fy, 8, arcade.color.WHITE, 1.5)
            
            arcade.draw_text(abbr, fx + 12, fy, arcade.color.WHITE, 10, bold=True, anchor_y="center")
    
    def draw_leaderboard(self):
        start_x, start_y = 130, SCREEN_HEIGHT - 70
        box_width = 240
        box_height = 28
        spacing = 32
        border_thickness = 3

        for i, abbr in enumerate(self.sorted_drivers):
            meta = self.driver_metadata.get(abbr, {})
            color = self.car_colors.get(abbr, arcade.color.GRAY)
            curr_y = start_y - (i * spacing)
            
            # Draw the Border (Team Color) 
            arcade.draw_rect_filled(
                arcade.rect.XYWH(start_x, curr_y, box_width, box_height), 
                color
            )
            # Draw the Inner Fill (Solid Black)
            arcade.draw_rect_filled(
                arcade.rect.XYWH(
                    start_x, curr_y, 
                    box_width - border_thickness, 
                    box_height - border_thickness
                ), 
                arcade.color.BLACK
            )
            # --- GAP LOGIC ---
            if i == 0:
                gap_display = "INTERVAL"
            else:
                # 1. Get the driver ahead of this one
                ahead_abbr = self.sorted_drivers[i-1]
                ahead_meta = self.driver_metadata.get(ahead_abbr, {})
                
                # 2. Calculate the physical distance between them in meters
                dist_now = meta.get('total_distance', 0.0)
                dist_ahead = ahead_meta.get('total_distance', 0.0)
                gap_meters = dist_ahead - dist_now
                
                # 3. Convert speed to m/s for the time calculation
                speed_kmh = meta.get('speed', 0.1) 
                speed_ms = max(speed_kmh / 3.6, 0.5) # Minimum speed to avoid infinity
                
                gap_seconds = gap_meters / speed_ms
                gap_display = f"+{max(0, gap_seconds):.1f}s"
            # -----------------------

            
            # Draw Rank & Abbreviation (Bold White)  
            arcade.draw_text(
                f"{i+1}  {abbr}", 
                start_x - 110, curr_y, 
                arcade.color.WHITE, 12, bold=True, anchor_y="center"
            )
            # Draw Gap Time (Bold White) [cite: 2026-02-20]
            arcade.draw_text(
                gap_display, 
                start_x + 110, curr_y, 
                arcade.color.WHITE, 11, bold=True, anchor_x="right", anchor_y="center"
            )
            
            
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

