# utils/helpers.py
import numpy as np
import sqlite3
import os

def get_screen_coords(x, y, rotation, track_scale, offset_x, offset_y):
    # 1. Rotate 
    rad = np.radians(rotation)
    tx = x * np.cos(rad) - y * np.sin(rad)
    ty = x * np.sin(rad) + y * np.cos(rad)

    # 2. Scale and Offset [cite: 2026-01-20]
    return (tx * track_scale) + offset_x, (ty * track_scale) + offset_y

def calculate_weather_frame_ratio(driver_abbrs, db_path):
    """
    Calculates the ratio: (Max Telemetry Rows) / (Weather Rows).
    Tells the main loop how many frames to wait before shifting the weather row.
    """
    max_telemetry_rows = 0
    weather_rows = 0

    try:
        # 1. Find the driver with the most frames to set the 'Master' duration
        for abbr in driver_abbrs:
            driver_db = os.path.join(db_path, f"{abbr}.db")
            if os.path.exists(driver_db):
                with sqlite3.connect(driver_db) as conn:
                    count = conn.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0]
                    if count > max_telemetry_rows:
                        max_telemetry_rows = count

        # 2. Get the total count of weather snapshots
        weather_db = os.path.join(db_path, "weather.db")
        if os.path.exists(weather_db):
            with sqlite3.connect(weather_db) as conn:
                weather_rows = conn.execute("SELECT COUNT(*) FROM weather").fetchone()[0]

        # 3. Calculate Ratio (Floor division)
        if weather_rows > 0:
            ratio = max_telemetry_rows // weather_rows
            return max(1, ratio) # Ensure ratio is at least 1
            
    except Exception as e:
        print(f"Error calculating frame ratio: {e}")
    
    return 1 

def prepare_track_layout(raw_x, raw_y, screen_width, screen_height, padding_left, rotation):
    """Fits the track perfectly within the available screen space."""
    draw_width = screen_width - padding_left - 100
    draw_height = screen_height - 150
    
    # 1. Rotate raw coordinates first to find the true 'footprint' [cite: 2026-01-20]
    rad = np.radians(rotation)
    x_rot = raw_x * np.cos(rad) - raw_y * np.sin(rad)
    y_rot = raw_x * np.sin(rad) + raw_y * np.cos(rad)
    
    # 2. Calculate the width and height of the track in 'data units' [cite: 2026-01-20]
    data_width = max(x_rot) - min(x_rot)
    data_height = max(y_rot) - min(y_rot)
    
    # 3. Calculate the scale based on the footprint, not track length [cite: 2026-01-20]
    # This prevents the 'zoomed in' look.
    scale_x = draw_width / data_width
    scale_y = draw_height / data_height
    track_scale = min(scale_x, scale_y) * 0.9  # 0.9 adds a little margin

    # 4. Apply scale and calculate offsets [cite: 2026-01-20]
    x_scaled = x_rot * track_scale
    y_scaled = y_rot * track_scale

    track_center_x = (min(x_scaled) + max(x_scaled)) / 2
    track_center_y = (min(y_scaled) + max(y_scaled)) / 2
    screen_center_x = padding_left + (draw_width / 2)
    screen_center_y = screen_height / 2

    offset_x = screen_center_x - track_center_x
    offset_y = screen_center_y - track_center_y
    
    track_points = [(xi + offset_x, yi + offset_y) for xi, yi in zip(x_scaled, y_scaled)]
    
    return track_points, offset_x, offset_y, track_scale