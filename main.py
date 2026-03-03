import arcade
import fastf1

from core.session_manager import SessionManager
from core.telemetry_processor import TelemetryProcessor
from core.track_utils import transform_track, clean_track_data


SCREEN_WIDTH = 1500
SCREEN_HEIGHT = 800
SCREEN_TITLE = "F1 Track Visualizer"

YEAR = 2023
GP = "Monza"
SESSION_TYPE = "R"
DRIVER = "VER"


class F1Visualizer(arcade.Window):
    def __init__(self):
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)

        arcade.set_background_color(arcade.color.BLACK)

        self.current_index = 0
        self.speed_array = None
        self.car_position = None
        self.track_points = None
        self.results = None
        
        self.current_speed_value = 0

        self.setup()

    def setup(self):
        # 1️⃣ Load session
        manager = SessionManager(YEAR, GP, SESSION_TYPE)
        self.results = manager.get_session_results()

        lap = manager.get_driver_laps(DRIVER, fastest_lap=True)
        if lap is None:
            print("No lap found.")
            return

        # 2️⃣ Process telemetry-
        processor = TelemetryProcessor(lap)

        x, y = processor.get_track_coordinates()
        x, y = clean_track_data(x, y)
        
        self.speed_array = processor.get_speed_data()
        
        if x is None:
            print("No telemetry.")
            return

        # 3️⃣ Transform track
        rotation = manager.get_circuit_rotation()

        # Define the size of the drawing area (the 'card' inside the window)
        # Higher padding = smaller track
        padding = 300 
        draw_width = SCREEN_WIDTH - padding
        draw_height = SCREEN_HEIGHT - padding

        # Transform and scale the raw data
        x, y = transform_track(
            x,
            y,
            draw_width,
            draw_height,
            rotation=rotation
        )

        # --- CENTER THE TRACK ---
        # 1. Find the current center of the track points
        track_center_x = (min(x) + max(x)) / 2
        track_center_y = (min(y) + max(y)) / 2

        # 2. Find the center of screen
        screen_center_x = SCREEN_WIDTH / 2
        screen_center_y = SCREEN_HEIGHT / 2

        # 3. Apply the difference as an offset to every point
        x = x + (screen_center_x - track_center_x)
        y = y + (screen_center_y - track_center_y)
        # ------------------------

        # Convert to list of (x, y) tuples for Arcade
        self.track_points = list(zip(x, y))
        
    def on_draw(self):
        self.clear()
        
        # 1. Draw the Leaderboard Tower on the left
        self.draw_leaderboard()
        
        # 2. Draw the Track
        if self.track_points:
            arcade.draw_line_strip(
                self.track_points,
                arcade.color.GREEN,
                5
            )
            
        # 3. Draw the Car and its Name Tag
        if self.car_position:
            arcade.draw_circle_filled(
                self.car_position[0],
                self.car_position[1],
                6,
                arcade.color.RED
            )
            
            # Draw the driver name
            arcade.draw_text(
                DRIVER,
                self.car_position[0] + 10, 
                self.car_position[1] + 10, 
                arcade.color.WHITE,
                10,
                bold=True
            )

        # 4. ADDED: Draw the Speedometer Card in the bottom right
        self.draw_speedometer()
    
    def on_update(self, delta_time):
        if not self.track_points or self.speed_array is None:
            return

        # 1. Get the total number of points in the track
        max_points = len(self.track_points)
        max_idx = min(max_points, len(self.speed_array)) - 1

        # 2. Calculate movement based on current speed
        # We cast current_index to int to look up the speed in your array
        current_speed = self.speed_array[int(self.current_index) % len(self.speed_array)]
        self.current_speed_value = current_speed
        movement = current_speed * delta_time * 0.05
        
        # 3. Increment index and use MODULO to loop back to 0 automatically
        self.current_index = (self.current_index + movement) % max_idx

        # 4. Interpolation logic for smooth movement between points
        base_index = int(self.current_index)
        next_index = (base_index + 1) % max_points

        t = self.current_index - base_index

        x1, y1 = self.track_points[base_index]
        x2, y2 = self.track_points[next_index]

        interp_x = x1 + (x2 - x1) * t
        interp_y = y1 + (y2 - y1) * t

        self.car_position = (interp_x, interp_y)

    def draw_leaderboard(self):
        if self.results is None:
            return

        # 1. RGB Tuple is the only safe way to avoid hex function errors
        box_color = (54, 113, 198)

        # Define Boundaries
        center_x = 100
        center_y = 100
        width = 150
        height = 50

        # 2. FIXED: Use draw_lrbt_rectangle_filled 
        # (Notice the order: Left, Right, Bottom, Top)
        arcade.draw_lrbt_rectangle_filled(
            center_x - (width / 2),   # Left
            center_x + (width / 2),   # Right
            center_y - (height / 2),  # Bottom
            center_y + (height / 2),  # Top
            box_color
        )

        # 3. Draw text centered
        arcade.draw_text(
            DRIVER, 
            center_x, 
            center_y, 
            arcade.color.WHITE, 
            font_size=14, 
            anchor_x="center", 
            anchor_y="center",
            bold=True
        )
    
    def draw_speedometer(self):
        center_x = SCREEN_WIDTH - 100
        center_y = SCREEN_HEIGHT - 100
        width = 150
        height = 75
        
        arcade.draw_lrbt_rectangle_filled(
            center_x - (width / 2),
            center_x + (width / 2),
            center_y - (height / 2),
            center_y + (height / 2),
            (30, 30, 30, 200)
        )
        
        # Draw the speed text
        arcade.draw_text(
            f"Speed: {int(self.current_speed_value)}",
            center_x,
            center_y,
            arcade.color.WHITE,
            font_size=14,
            anchor_x="center",
            anchor_y="center",
            bold=True   
        )               
        arcade.draw_text(   
            "KM/H",
            center_x,
            center_y - 20,
            arcade.color.GAINSBORO,
            font_size=10,
            anchor_x="center",
            anchor_y="center",
            bold=True
        )        
                    
def main():
    fastf1.Cache.enable_cache("cache")
    window = F1Visualizer()
    arcade.run()

if __name__ == "__main__":
    main()
    