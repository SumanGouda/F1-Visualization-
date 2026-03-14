# Starter file
import arcade
import math

def draw_leaderboard(sorted_drivers, driver_metadata, car_colors, screen_height):
    # Moved start_y down from -70 to -120 to 'drag' it down the screen
    start_x, start_y = 130, screen_height - 120 
    box_width = 240
    box_height = 28
    spacing = 32
    border_thickness = 3

    for i, abbr in enumerate(sorted_drivers):
        meta = driver_metadata.get(abbr, {})
        color = car_colors.get(abbr, arcade.color.GRAY)
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
            ahead_abbr = sorted_drivers[i-1]
            ahead_meta = driver_metadata.get(ahead_abbr, {})
            dist_now = meta.get('total_distance', 0.0)
            dist_ahead = ahead_meta.get('total_distance', 0.0)
            gap_meters = dist_ahead - dist_now
            speed_kmh = meta.get('speed', 0.1) 
            speed_ms = max(speed_kmh / 3.6, 0.5) 
            gap_seconds = gap_meters / speed_ms
            gap_display = f"+{max(0, gap_seconds):.1f}s"
        
        # Draw Text Elements
        arcade.draw_text(
            f"{i+1}  {abbr}", 
            start_x - 110, curr_y, 
            arcade.color.WHITE, 12, bold=True, anchor_y="center"
        )
        arcade.draw_text(
            gap_display, 
            start_x + 110, curr_y, 
            arcade.color.WHITE, 11, bold=True, anchor_x="right", anchor_y="center"
        )

def draw_lap_number(sorted_drivers, driver_metadata, screen_width, screen_height, total_laps): 
    start_x = screen_width - 150 
    start_y = screen_height - 70
    
    box_width = 80
    box_height = 50  
    border_thickness = 3
    
    # 2. Extract Data  
    if not sorted_drivers:
        return
        
    lead_abbr = sorted_drivers[0]
    meta = driver_metadata.get(lead_abbr, {}) 
    lap_number = int(meta.get('lap_number', 1))
    
    # 3. Draw the Card Style 
    arcade.draw_rect_filled(
        arcade.rect.XYWH(start_x, start_y, box_width, box_height), 
        arcade.color.WHITE
    )
    # Inner Fill (Solid Black)
    arcade.draw_rect_filled(
        arcade.rect.XYWH(
            start_x, start_y, 
            box_width - border_thickness, 
            box_height - border_thickness
        ), 
        arcade.color.BLACK
    )

    # 4. Draw Lap Text
    arcade.draw_text(
        f"{lap_number} / {total_laps}\nLAPS", 
        start_x, 
        start_y, 
        arcade.color.WHITE, 
        14, 
        bold=True, 
        anchor_x="center", 
        anchor_y="center",
        multiline=True,       
        width=box_width,     
        align="center"     
    )
 
def draw_corners(corner_data, rotation, track_scale, offset_x, offset_y):
    """
    Renders corner markers and labels slightly offset from the track line.
    """
    if not corner_data:
        return

    # Pre-calculate rotation math once to save FPS [cite: 2026-03-07]
    rad = math.radians(rotation)
    cos_val = math.cos(rad)
    sin_val = math.sin(rad)
    
    # Distance to push the marker away from the track (in pixels)
    push_distance = 15 

    for corner in corner_data:
        raw_x = corner['x']
        raw_y = corner['y']
        
        # 1. Rotate the raw coordinates
        rx = raw_x * cos_val - raw_y * sin_val
        ry = raw_x * sin_val + raw_y * cos_val
        
        # 2. Basic Scale and Offset
        fx = (rx * track_scale) + offset_x
        fy = (ry * track_scale) + offset_y

        # 3. Apply "Side-of-Track" Offset [cite: 2026-03-07]
        # We use the 'angle' provided by FastF1 to determine the 'outside' direction
        # Angle is in degrees, convert to radians
        angle_rad = math.radians(corner.get('angle', 0) + rotation)
        
        # Adjust fx and fy to move them slightly off-center from the track line
        fx += math.cos(angle_rad) * push_distance
        fy += math.sin(angle_rad) * push_distance
        
        # 4. Draw Marker (Yellow Dot)
        arcade.draw_circle_filled(fx, fy, 3, arcade.color.YELLOW)
        
        # 5. Draw Text (Simplified for better performance)
        label = corner['number']
        arcade.draw_text(
            label, 
            fx, 
            fy + 8, # Positioned slightly above the dot
            arcade.color.WHITE, 
            9, 
            bold=True, 
            anchor_x="center",
            font_name="Kenney Future" # Optional: matches your card style
        )

def draw_weather_card(weather_row, screen_width, screen_height):
    if weather_row is None:
        return

    # Card Dimensions and Position (Bottom Left)
    box_width, box_height = 240, 110
    center_x, center_y = 145, 75 

    # Draw Card Border and Background
    arcade.draw_rect_filled(arcade.rect.XYWH(center_x, center_y, box_width, box_height), arcade.color.WHITE)
    arcade.draw_rect_filled(arcade.rect.XYWH(center_x, center_y, box_width - 4, box_height - 4), arcade.color.BLACK)

    try:
        # Extracting data from the sqlite3.Row object
        air_temp = f"{weather_row['AirTemp']}°C"
        track_temp = f"{weather_row['TrackTemp']}°C"
        hum = f"{weather_row['Humidity']}%"
        wind = f"{weather_row['WindSpeed']}m/s"
        
        is_raining = weather_row['Rainfall']
        status_text = "RAIN" if is_raining else "DRY"
        status_color = arcade.color.SKY_BLUE if is_raining else arcade.color.LIGHT_GREEN
    except (KeyError, TypeError):
        return

    # Positioning Constants
    left_align = center_x - (box_width / 2) + 15
    top_y = center_y + (box_height / 2) - 20

    # Header
    arcade.draw_text("SESSION WEATHER", left_align, top_y, arcade.color.YELLOW, 10, bold=True)
    
    # Status Indicator (Circle + Text)
    arcade.draw_circle_filled(center_x + (box_width/2) - 65, top_y + 5, 5, status_color)
    arcade.draw_text(status_text, center_x + (box_width/2) - 55, top_y, status_color, 10, bold=True)

    # Weather Details Grid
    row1 = f"AIR TEMP: {air_temp:>8} | TRACK: {track_temp:>8}"
    row2 = f"HUMIDITY: {hum:>8} | WIND: {wind:>8}"
    
    arcade.draw_text(row1, left_align, top_y - 35, arcade.color.WHITE, 9, font_name="Courier New")
    arcade.draw_text(row2, left_align, top_y - 55, arcade.color.WHITE, 9, font_name="Courier New")
                   
class UIRenderer:
    def __init__(self, width, height):
        self.width = width
        self.height = height

    def draw_driver_info(self, driver_name, team_name):
        arcade.draw_text(
            f"Driver: {driver_name}",
            20,
            self.height - 40,
            arcade.color.WHITE,
            16
        )
        arcade.draw_text(
            f"Team: {team_name}",
            20,
            self.height - 70,
            arcade.color.LIGHT_GRAY,
            14
        )

    def draw_speed(self, speed):
        arcade.draw_text(
            f"{int(speed)} km/h",
            self.width - 200,
            40,
            arcade.color.RED,
            28,
            bold=True
        )

    def draw_lap_time(self, lap_time):
        arcade.draw_text(
            f"Lap Time: {lap_time}",
            20,
            self.height - 100,
            arcade.color.YELLOW,
            14
        )