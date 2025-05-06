import requests

OPENWEATHER_API_KEY = "5c3bc13964691a682f63c98f718091e5"

def get_weather_data(lat, lon):
    """
    Fetch weather data from OpenWeatherMap API.
    """
    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/weather?"
            f"lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
        )
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching weather data: {e}")
        return {}