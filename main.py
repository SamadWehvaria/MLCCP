import requests
import pandas as pd
import joblib
from fetch_tomtom import get_traffic_data, get_incident_data
from fetch_openweather import get_weather_data

TOMTOM_API_KEY = "I964aUjk3OZ8GBAIMd7tqtjOU5Bs76Nm"
OPENWEATHERMAP_API_KEY = "5c3bc13964691a682f63c98f718091e5"

# Load the trained model, scaler, and label encoder
model = joblib.load('congestion_model.pkl')
scaler = joblib.load('scaler.pkl')
le = joblib.load('label_encoder.pkl')

def geocode_city(city_name):
    """
    Convert city name to latitude, longitude, and bounding box using TomTom Geocoding API.
    """
    try:
        search_url = f"https://api.tomtom.com/search/2/geocode/{city_name}.json?key={TOMTOM_API_KEY}&limit=1"
        response = requests.get(search_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get('results'):
            result = data['results'][0]
            lat = result['position']['lat']
            lon = result['position']['lon']
            bbox = ",".join(map(str, [lon-0.2, lat-0.2, lon+0.2, lat+0.2]))
            print(f"Geocoded {city_name}: lat={lat}, lon={lon}, bbox={bbox}")
            return lat, lon, bbox
        return None, None, None
    except requests.exceptions.RequestException as e:
        print(f"Error geocoding city: {e}")
        if e.response is not None and "InsufficientFunds" in e.response.text:
            raise Exception("TomTom API: Insufficient credits. Please add credits to your account.")
        return None, None, None

def get_pois(lat, lon, category="7315"):  # 7315 = Hospitals
    """
    Fetch nearby points of interest (e.g., hospitals) using TomTom Nearby Search API.
    """
    try:
        search_url = (
            f"https://api.tomtom.com/search/2/nearbySearch/.json?"
            f"lat={lat}&lon={lon}&radius=5000&categorySet={category}&key={TOMTOM_API_KEY}"
        )
        response = requests.get(search_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return {result['id']: {"name": result['poi']['name'], "lat": result['position']['lat'], "lon": result['position']['lon']}
                for result in data.get('results', []) if 'poi' in result}
    except requests.exceptions.RequestException as e:
        print(f"Error fetching POIs: {e}")
        if e.response is not None and "InsufficientFunds" in e.response.text:
            raise Exception("TomTom API: Insufficient credits. Please add credits to your account.")
        return {}

def get_all_data(city_name, lat, lon, bbox):
    """
    Fetch all live data (traffic flow, incidents, weather) for given location and bbox.
    """
    try:
        traffic = get_traffic_data(bbox, lat, lon)
        incidents = get_incident_data(bbox)
        weather = get_weather_data(lat, lon)
        print(f"Incidents fetched: {len(incidents.get('incidents', []))}")
        return {
            "traffic": traffic,
            "incidents": incidents,
            "weather": weather,
            "city_name": city_name
        }
    except Exception as e:
        print(f"Error fetching data: {e}")
        return {"traffic": {}, "incidents": {"incidents": []}, "weather": {}, "city_name": city_name}

def estimate_congestion(traffic, weather, incidents, city_name):
    """
    Estimate congestion level using the trained machine learning model.
    Returns congestion level as a string (Low, Medium, High).
    """
    try:
        current_speed = traffic.get('currentSpeed', 0)
        free_flow_speed = traffic.get('freeFlowSpeed', 1)
        incident_count = len(incidents.get('incidents', []))
        temperature = weather.get('main', {}).get('temp', 0)
        wind_speed = weather.get('wind', {}).get('speed', 0)
        weather_condition = weather.get('weather', [{}])[0].get('description', 'clear').lower()
        weather_map = {
            'clear': 'clear', 'partly cloudy': 'partly cloudy', 'cloudy': 'cloudy',
            'rain': 'rain', 'snow': 'snow', 'fog': 'fog', 'mist': 'mist', 'storm': 'storm'
        }
        weather_condition = weather_map.get(weather_condition, 'clear')

        # Prepare input data with feature names matching training
        input_data = pd.DataFrame({
            'location': [city_name],
            'current_speed': [current_speed],
            'free_flow_speed': [free_flow_speed],
            'incident_count': [incident_count],
            'temperature': [temperature],
            'wind_speed': [wind_speed],
            'weather_condition': [weather_condition]
        })

        # One-hot encode categorical features
        input_data = pd.get_dummies(input_data, columns=['location', 'weather_condition'], drop_first=True)

        # Align with training columns (model.feature_names_in_)
        input_data = input_data.reindex(columns=model.feature_names_in_, fill_value=0)

        # Scale numerical features with proper feature names
        numerical_cols = ['current_speed', 'free_flow_speed', 'incident_count', 'temperature', 'wind_speed']
        numerical_data = input_data[numerical_cols]  # Keep as DataFrame to preserve column names
        scaled_data = scaler.transform(numerical_data)
        for i, col in enumerate(numerical_cols):
            input_data[col] = scaled_data[:, i]

        # Predict congestion level
        prediction = model.predict(input_data)
        congestion_level = le.inverse_transform(prediction)[0]

        return congestion_level
    except Exception as e:
        print(f"Error estimating congestion: {e}")
        return "Unknown"

def get_route_with_traffic(start_lat, start_lon, end_lat, end_lon, city_name):
    """
    Fetch route from start to end and estimate traffic conditions for segments.
    Returns route segments with coordinates and traffic status.
    """
    try:
        route_url = (
            f"https://api.tomtom.com/routing/1/calculateRoute/"
            f"{start_lat},{start_lon}:{end_lat},{end_lon}/json?"
            f"key={TOMTOM_API_KEY}&routeType=shortest&travelMode=car&traffic=true"
        )
        response = requests.get(route_url, timeout=10)
        response.raise_for_status()
        route_data = response.json()
        routes = route_data.get('routes', [])
        if not routes:
            print("No routes returned from API.")
            return None

        route = routes[0]
        travel_time_minutes = route['summary']['travelTimeInSeconds'] / 60
        distance_km = route['summary']['lengthInMeters'] / 1000

        # Collect all coordinates for the full route
        coordinates = []
        for leg in route['legs']:
            for point in leg['points']:
                coordinates.append([point['latitude'], point['longitude']])

        # Ensure coordinates start and end exactly at the provided locations
        if coordinates:
            coordinates[0] = [start_lat, start_lon]  # Force start point
            coordinates[-1] = [end_lat, end_lon]     # Force end point

        # Create segments with smaller granularity, ensuring continuity
        segments = []
        segment_size = max(2, len(coordinates) // 10)  # Dynamic segment size based on route length
        i = 0
        while i < len(coordinates):
            # Take segment up to segment_size, but ensure we don't overshoot
            end_idx = min(i + segment_size, len(coordinates))
            segment_coords = coordinates[i:end_idx]
            if len(segment_coords) < 2:
                break  # Skip if segment is too small

            # Estimate congestion for this segment
            mid_point = segment_coords[len(segment_coords) // 2]
            traffic_data = get_traffic_data(None, mid_point[0], mid_point[1])
            congestion_level = estimate_congestion(traffic_data, {}, {}, city_name) if traffic_data else "Unknown"
            segments.append({
                'coordinates': segment_coords,
                'congestion_level': congestion_level
            })

            # Move to the next segment, ensuring overlap to avoid gaps
            i += segment_size - 1

        # Ensure the last segment includes the end point
        if coordinates and i < len(coordinates):
            last_segment = coordinates[i-1:] if i > 0 else coordinates
            if len(last_segment) >= 2:
                mid_point = last_segment[len(last_segment) // 2]
                traffic_data = get_traffic_data(None, mid_point[0], mid_point[1])
                congestion_level = estimate_congestion(traffic_data, {}, {}, city_name) if traffic_data else "Unknown"
                segments.append({
                    'coordinates': last_segment,
                    'congestion_level': congestion_level
                })

        return {
            'segments': segments,
            'travel_time_minutes': travel_time_minutes,
            'distance_km': distance_km
        }
    except requests.exceptions.RequestException as e:
        print(f"Error fetching route: {e} for URL: {route_url}")
        if e.response is not None and "InsufficientFunds" in e.response.text:
            raise Exception("TomTom API: Insufficient credits. Please add credits to your account.")
        return None
