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
if 'map_zoom' not in st.session_state:
    st.session_state.map_zoom = 12
if 'map_center' not in st.session_state:
    st.session_state.map_center = [51.51, -0.12]
if 'route_options' not in st.session_state:
    st.session_state.route_options = []
if 'selected_route' not in st.session_state:
    st.session_state.selected_route = 0  # Default to primary route

# Sidebar for user-friendly settings
st.sidebar.header("📍 Location & Destination")
city = st.sidebar.text_input("Search City", value="London", help="Enter a city name (e.g., London, Karachi, New York)")
if st.sidebar.button("Set Location"):
    lat, lon, bbox = geocode_city(city)
    if lat and lon:
        st.session_state.current_lat = lat
        st.session_state.current_lon = lon
        st.session_state.bbox = bbox
        st.session_state.pois = get_pois(lat, lon)
        st.session_state.map_center = [lat, lon]
        st.session_state.map_initialized = False
        st.session_state.route_options = []  # Reset routes on location change
        st.rerun()

# Destination selection
st.sidebar.subheader("🏁 Select Destination")
dest_option = st.sidebar.selectbox("Choose a Destination", ["Click Map to Set"] + [f"{poi['name']} ({poi['lat']}, {poi['lon']})" for poi_id, poi in st.session_state.pois.items()])
if dest_option != "Click Map to Set":
    dest_name, dest_coords = dest_option.rsplit(" (", 1)
    dest_lat, dest_lon = map(float, dest_coords.rstrip(")").split(", "))
    st.session_state.dest_lat = dest_lat
    st.session_state.dest_lon = dest_lon
    st.session_state.route_options = []  # Reset routes on destination change
if st.sidebar.button("Calculate Route"):
    st.rerun()

# Refresh button
if st.button("🔄 Refresh Data"):
    lat, lon, bbox = st.session_state.current_lat, st.session_state.current_lon, st.session_state.get('bbox', "51.50,-0.15,51.52,-0.10")
    st.session_state.pois = get_pois(lat, lon)
    st.session_state.map_initialized = False
    st.session_state.route_options = []
    st.rerun()

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
    # Fetch primary route if no routes are cached
    if not st.session_state.route_options:
        route_options = get_route_with_traffic(lat, lon, st.session_state.dest_lat, st.session_state.dest_lon, city, alternatives=False)
        if route_options:
            primary_route = route_options[0]
            # If primary route has high congestion, fetch alternatives
            if primary_route['overall_congestion_level'] == "High":
                st.warning("High congestion detected on primary route. Fetching alternative routes...")
                route_options = get_route_with_traffic(lat, lon, st.session_state.dest_lat, st.session_state.dest_lon, city, alternatives=True)
            st.session_state.route_options = route_options if route_options else []

    # Display route options
    if st.session_state.route_options:
        route_labels = [
            f"Route {r['route_id'] + 1}: {r['travel_time_minutes']:.1f} mins, {r['distance_km']:.1f} km, Congestion: {r['overall_congestion_level']}"
            for r in st.session_state.route_options
        ]
        selected_route_label = st.selectbox("Select Route", route_labels, index=st.session_state.selected_route)
        st.session_state.selected_route = route_labels.index(selected_route_label)
        selected_route = st.session_state.route_options[st.session_state.selected_route]
        st.info(f"Estimated Travel Time: {selected_route['travel_time_minutes']:.1f} minutes ({selected_route['distance_km']:.1f} km)")
    else:
        st.warning("Unable to calculate travel time.")
else:
    st.write("Set a destination to see travel time.")

# Map with interactive features
st.subheader("🗺️ Live Traffic Map")
m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom, control_scale=True)

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

# Add selected route with traffic conditions
if st.session_state.dest_lat and st.session_state.dest_lon and st.session_state.route_options:
    selected_route = st.session_state.route_options[st.session_state.selected_route]
    all_coords = []
    for segment in selected_route['segments']:
        all_coords.extend(segment['coordinates'])
        color = {'Low': 'green', 'Medium': 'orange', 'High': 'red'}.get(segment['congestion_level'], 'gray')
        folium.PolyLine(
            locations=segment['coordinates'],
            color=color,
            weight=5,
            opacity=0.7,
            tooltip=f"Congestion: {segment['congestion_level']}"
        ).add_to(m)
    if all_coords:
        folium.PolyLine(
            locations=all_coords,
            color='blue',
            weight=2,
            opacity=0.5,
            tooltip="Overall Route"
        ).add_to(m)

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
map_data = st_folium(m, width=700, height=400, key="map", returned_objects=["last_clicked", "center", "zoom"])
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
            st.session_state.route_options = []
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

# Update map zoom and center
if map_data:
    if map_data.get('zoom') and map_data['zoom'] != st.session_state.map_zoom:
        st.session_state.map_zoom = map_data['zoom']
    if map_data.get('center') and map_data['center'] != st.session_state.map_center:
        st.session_state.map_center = [map_data['center']['lat'], map_data['center']['lng']]

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