import streamlit as st
import folium
from streamlit_folium import st_folium
from main import geocode_city, get_all_data, estimate_congestion, get_route_with_traffic, get_pois

st.set_page_config(layout="wide")
st.markdown("""
    <h1 style='text-align: center; color: #2E86AB;'>🚦 Smart Traffic Monitoring & Congestion Dashboard</h1>
""", unsafe_allow_html=True)

# Initialize session state
if 'current_lat' not in st.session_state:
    st.session_state.current_lat = 51.51
if 'current_lon' not in st.session_state:
    st.session_state.current_lon = -0.12
if 'dest_lat' not in st.session_state:
    st.session_state.dest_lat = None
if 'dest_lon' not in st.session_state:
    st.session_state.dest_lon = None
if 'pois' not in st.session_state:
    st.session_state.pois = {}
if 'last_clicked' not in st.session_state:
    st.session_state.last_clicked = None
if 'confirm_switch' not in st.session_state:
    st.session_state.confirm_switch = False
if 'map_initialized' not in st.session_state:
    st.session_state.map_initialized = False

# Sidebar for user-friendly settings
st.sidebar.header("📍 Location & Destination")
city = st.sidebar.text_input("Search City", value="London", help="Enter a city name (e.g., London, Karachi, New York)")
if st.sidebar.button("Set Location"):
    try:
        lat, lon, bbox = geocode_city(city)
        if lat and lon:
            st.session_state.current_lat = lat
            st.session_state.current_lon = lon
            st.session_state.bbox = bbox
            st.session_state.pois = get_pois(lat, lon)
            st.session_state.map_initialized = False
            st.rerun()
    except Exception as e:
        if "Insufficient credits" in str(e):
            st.sidebar.error("TomTom API error: Insufficient credits. Please add credits to your account on the TomTom developer portal.")
        else:
            st.sidebar.error(f"Error setting location: {e}")

# Destination selection
st.sidebar.subheader("🏁 Select Destination")
dest_option = st.sidebar.selectbox("Choose a Destination", ["Click Map to Set"] + [f"{poi['name']} ({poi['lat']}, {poi['lon']})" for poi_id, poi in st.session_state.pois.items()])
if dest_option != "Click Map to Set":
    dest_name, dest_coords = dest_option.rsplit(" (", 1)
    dest_lat, dest_lon = map(float, dest_coords.rstrip(")").split(", "))
    st.session_state.dest_lat = dest_lat
    st.session_state.dest_lon = dest_lon
if st.sidebar.button("Calculate Route"):
    st.rerun()

# Refresh button
if st.button("🔄 Refresh Data"):
    try:
        lat, lon, bbox = st.session_state.current_lat, st.session_state.current_lon, st.session_state.get('bbox', "51.50,-0.15,51.52,-0.10")
        st.session_state.pois = get_pois(lat, lon)
        st.session_state.map_initialized = False
        st.rerun()
    except Exception as e:
        if "Insufficient credits" in str(e):
            st.error("TomTom API error: Insufficient credits. Please add credits to your account on the TomTom developer portal.")
        else:
            st.error(f"Error refreshing data: {e}")

# Fetch live data (non-reactive block)
@st.cache_data(ttl=300)  # Cache for 5 minutes to reduce API calls
def fetch_data(lat, lon, bbox, city):
    return get_all_data(city, lat, lon, bbox)

lat, lon, bbox = st.session_state.current_lat, st.session_state.current_lon, st.session_state.get('bbox', "51.50,-0.15,51.52,-0.10")
data = fetch_data(lat, lon, bbox, city)
traffic = data["traffic"]
incidents = data["incidents"]
weather = data["weather"]

# Estimate congestion
congestion_level = estimate_congestion(traffic, weather, incidents, city)

# Traffic Status
st.subheader("📊 Traffic Status")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Current Speed (km/h)", traffic.get('currentSpeed', 0))
with col2:
    st.metric("Free Flow Speed (km/h)", traffic.get('freeFlowSpeed', 0))
with col3:
    st.metric("Congestion Level", congestion_level)

# Weather Status
st.subheader("🌦️ Current Weather")
col1, col2, col3 = st.columns(3)
with col1:
    st.write(f"**Condition:** {weather.get('weather', [{}])[0].get('description', 'N/A')}")
with col2:
    st.write(f"**Temperature:** {weather.get('main', {}).get('temp', 'N/A')} °C")
with col3:
    st.write(f"**Wind Speed:** {weather.get('wind', {}).get('speed', 'N/A')} m/s")

# Travel Time and Route
st.subheader("🕒 Travel Information")
if st.session_state.dest_lat and st.session_state.dest_lon:
    try:
        route_data = get_route_with_traffic(lat, lon, st.session_state.dest_lat, st.session_state.dest_lon, city)
        if route_data:
            st.info(f"Estimated Travel Time: {route_data['travel_time_minutes']:.1f} minutes ({route_data['distance_km']:.1f} km)")
        else:
            st.warning("Unable to calculate travel time. Check API key or permissions.")
    except Exception as e:
        if "Insufficient credits" in str(e):
            st.error("TomTom API error: Insufficient credits. Please add credits to your account on the TomTom developer portal.")
        else:
            st.error(f"Error calculating route: {e}")
else:
    st.write("Set a destination to see travel time.")

# Map with interactive features
st.subheader("🗺️ Live Traffic Map")
m = folium.Map(location=[lat, lon], zoom_start=12, control_scale=True)

# Add current location marker (car icon)
folium.Marker(
    location=[lat, lon],
    icon=folium.Icon(icon="car", prefix="fa", color="blue"),
    tooltip="Your Location"
).add_to(m)

# Add destination marker (flag icon)
if st.session_state.dest_lat and st.session_state.dest_lon:
    folium.Marker(
        location=[st.session_state.dest_lat, st.session_state.dest_lon],
        icon=folium.Icon(icon="flag", prefix="fa", color="green"),
        tooltip="Destination"
    ).add_to(m)

# Add route with traffic conditions
if st.session_state.dest_lat and st.session_state.dest_lon:
    try:
        route_data = get_route_with_traffic(lat, lon, st.session_state.dest_lat, st.session_state.dest_lon, city)
        if route_data:
            all_coords = []
            # Draw congestion segments first (broader lines)
            for segment in route_data['segments']:
                all_coords.extend(segment['coordinates'])
                color_map = {'Low': '#008000', 'Medium': '#FFFF00', 'High': '#FF0000', 'Unknown': '#808080'}
                color = color_map.get(segment['congestion_level'], '#808080')  # Grey for unknown or alternate
                folium.PolyLine(
                    locations=segment['coordinates'],
                    color=color,
                    weight=8,  # Thicker line for congestion segments
                    opacity=0.8,
                    tooltip=f"Congestion: {segment['congestion_level']}"
                ).add_to(m)
            # Draw the overall route on top (slightly thinner, dark blue)
            if all_coords:
                folium.PolyLine(
                    locations=all_coords,
                    color='#00008B',  # Dark blue for overall route
                    weight=4,  # Slightly thinner than segment lines
                    opacity=0.6,
                    tooltip="Overall Route"
                ).add_to(m)
        else:
            st.warning("Route data unavailable due to API error.")
    except Exception as e:
        if "Insufficient credits" in str(e):
            st.error("TomTom API error: Insufficient credits. Please add credits to your account on the TomTom developer portal.")
        else:
            st.error(f"Error displaying route: {e}")

# Add incidents
for incident in incidents.get('incidents', []):
    point = incident.get('geometry', {}).get('coordinates', [[lon, lat]])[0]
    description = incident.get('properties', {}).get('description', 'No description')
    folium.Marker(
        location=[point[1], point[0]],
        popup=description,
        icon=folium.Icon(color='red', icon='exclamation-triangle')
    ).add_to(m)

# Handle click events with confirmation
map_data = st_folium(m, width=700, height=400, key="map")
if map_data and map_data.get('last_clicked') and not st.session_state.confirm_switch:
    clicked_lat = map_data['last_clicked']['lat']
    clicked_lng = map_data['last_clicked']['lng']
    st.session_state.last_clicked = {'lat': clicked_lat, 'lng': clicked_lng}
    st.warning("Would you like to set this location as your destination?")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Yes", key="confirm_yes"):
            st.session_state.dest_lat = clicked_lat
            st.session_state.dest_lon = clicked_lng
            st.session_state.confirm_switch = True
            st.rerun()
    with col2:
        if st.button("No", key="confirm_no"):
            st.session_state.confirm_switch = True
            st.rerun()
elif st.session_state.confirm_switch and st.session_state.last_clicked:
    clicked_lat = st.session_state.last_clicked['lat']
    clicked_lng = st.session_state.last_clicked['lng']
    click_info = f"Destination set to: {clicked_lat:.6f}, {clicked_lng:.6f}"
    poi_name = None
    for poi_id, poi in st.session_state.pois.items():
        poi_lat, poi_lon = poi['lat'], poi['lon']
        if abs(poi_lat - clicked_lat) < 0.01 and abs(poi_lon - clicked_lng) < 0.01:
            poi_name = poi['name']
            break
    if poi_name:
        click_info += f"\nThis is a: {poi_name}"
    else:
        click_info += "\nNo known points of interest nearby."
    for incident in incidents.get('incidents', []):
        point = incident.get('geometry', {}).get('coordinates', [[lon, lat]])[0]
        if abs(point[1] - clicked_lat) < 0.01 and abs(point[0] - clicked_lng) < 0.01:
            click_info += f"\nNear Incident: {incident.get('properties', {}).get('description', 'Unknown')}"
            break
    st.write(click_info)
    st.session_state.confirm_switch = False

# Alerts
st.subheader("🚨 Alerts")
incident_list = incidents.get('incidents', [])
if incident_list:
    for incident in incident_list[:3]:
        category = incident.get('properties', {}).get('iconCategory', 'Unknown')
        description = incident.get('properties', {}).get('description', 'No description')
        st.info(f"Incident: {category} - {description}")
else:
    st.success("✅ No incidents reported.")
