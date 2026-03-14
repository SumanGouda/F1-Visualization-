import fastf1


class SessionManager:

    def __init__(self, year, gp, session_type):
        self.session = None
        self.year = year           
        self.gp = gp
        self.weather_df = None

        try:
            self.session = fastf1.get_session(year, gp, session_type)
            self.session.load()
        except Exception as e:
            print(f"Error loading session: {e}")

    def get_driver_laps(self, driver, fastest_lap=False):
        if self.session is None:
            return None

        try:
            driver_laps = self.session.laps.pick_driver(driver)

            if driver_laps.empty:
                print(f"No laps found for driver {driver}")
                return None

            return driver_laps.pick_fastest() if fastest_lap else driver_laps

        except Exception as e:
            print(f"Error retrieving driver data: {e}")
            return None

    def get_session_fastest_lap(self):
        if self.session is None:
            return None

        try:
            return self.session.laps.pick_fastest()
        except Exception as e:
            print(f"Error retrieving fastest lap: {e}")
            return None

    def get_session_results(self):
        if self.session is None:
            return None

        try:
            return self.session.results[
                ['DriverNumber', 'Abbreviation', 'TeamName',
                 'TeamColor', 'Position', 'GridPosition',
                 'Time', 'Status', 'Points', 'Laps']
            ]
        except Exception as e:
            print(f"Error retrieving session results: {e}")
            return None

    def get_driver_info(self, driver):
        if self.session is None:
            return None

        try:
            return self.session.get_driver(driver)
        except Exception as e:
            print(f"Error retrieving driver info: {e}")
            return None

    def get_team_info(self, team):
        results = self.get_session_results()
        if results is None:
            return None

        team_data = results[results['TeamName'].str.lower() == team.lower()]
        team_data = team_data[
            ['DriverNumber', 'Abbreviation', 'TeamName',
             'TeamColor', 'Position', 'GridPosition',
             'Time', 'Status', 'Points', 'Laps']
        ]

        if team_data.empty:
            print(f"No data found for team {team}")
            return None

        return team_data

    def get_weather_data(self):
        if self.session is None:
            return None

        try:
            return self.session.weather_data
        except Exception as e:
            print(f"Error retrieving weather data: {e}")
            return None

    def get_circuit_rotation(self):
        if self.session is None:
            return None

        try:
            circuit_info = self.session.get_circuit_info()
            return circuit_info.rotation
        except Exception as e:
            print(f"Error retrieving circuit rotation: {e}")
            return None

    def get_corner_data(self):
        if self.session is None:
            return None

        try:
            circuit_info = self.session.get_circuit_info()
            corners = []
            for _, corner in circuit_info.corners.iterrows():
                corners.append({
                    "number": str(corner['Number']),
                    "x": float(corner['X']),
                    "y": float(corner['Y']),
                    "angle": float(corner['Angle']),
                    "distance": float(corner['Distance'])
                })
            return corners
        except Exception as e:
            print(f"Error retrieving corner data: {e}")
            return None

    