import requests

TOMTOM_API_KEY = "zy5PaNZytiCexgFfx4zdvIYPrpfKAal3"

def get_traffic_data(bbox, lat, lon):
    """
    Fetch traffic flow data from TomTom API for the given point.
    """
    try:
        flow_url = (
            f"https://api.tomtom.com/traffic/services/4/flowSegmentData/relative0/10/json?"
            f"point={lat},{lon}&key={TOMTOM_API_KEY}"
        )
        response = requests.get(flow_url, timeout=10)
        response.raise_for_status()
        return response.json().get("flowSegmentData", {})
    except requests.exceptions.RequestException as e:
        print(f"Error fetching traffic flow data: {e}")
        return {}

def get_incident_data(bbox):
    """
    Fetch traffic incident data from TomTom API for the given bounding box.
    """
    try:
        incident_url = (
            f"https://api.tomtom.com/traffic/services/5/incidentDetails?"
            f"bbox={bbox}&key={TOMTOM_API_KEY}&fields=all&language=en"
        )
        response = requests.get(incident_url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching traffic incidents: {e}")
        return {"incidents": []}