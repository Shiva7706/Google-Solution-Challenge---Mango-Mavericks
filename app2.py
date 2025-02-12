import streamlit as st
import osmnx as ox
import networkx as nx
import folium
from streamlit_folium import folium_static
import google.generativeai as genai
from datetime import datetime

# Configure Gemini AI
GEMINI_API_KEY = "AIzaSyDDvsc7lmGKLf52TajecWA4dSK_eV_ckyI"
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# Cache the graph loading (modified with simplify=False)
@st.cache_data(ttl=3600)
def load_city_graph(city_name):
    return ox.graph_from_place(city_name, network_type="drive", simplify=False)

# Cache geocoding results
@st.cache_data(ttl=3600)
def cached_geocode(location):
    return ox.geocode(location)

def get_traffic_weight(road_type, current_hour):
    base_weights = {
        'motorway': 1.0,
        'trunk': 1.2,
        'primary': 1.3,
        'secondary': 1.4,
        'tertiary': 1.5,
        'residential': 1.6,
        'unclassified': 1.8
    }
    
    rush_hours = [8, 9, 17, 18, 19]
    time_multiplier = 1.5 if current_hour in rush_hours else 1.0
    road_type = str(road_type).lower() if road_type else 'unclassified'
    return next((w * time_multiplier for k, w in base_weights.items() if k in road_type), 1.8)

def plot_route_on_map(G, route):
    route_edges = list(zip(route[:-1], route[1:]))
    
    center_lat = G.nodes[route[0]]['y']
    center_lon = G.nodes[route[0]]['x']
    m = folium.Map(location=[center_lat, center_lon], 
                  zoom_start=13,
                  tiles='cartodbpositron')
    
    coordinates = []
    for u, v in route_edges:
        edge_coords = []
        try:
            data = G.get_edge_data(u, v)[0]
            if 'geometry' in data:
                coords = list(data['geometry'].coords)
                edge_coords.extend(coords)
            else:
                # Correct coordinate order (lon, lat)
                start_coords = (G.nodes[u]['x'], G.nodes[u]['y'])
                end_coords = (G.nodes[v]['x'], G.nodes[v]['y'])
                edge_coords.extend([start_coords, end_coords])
        except (KeyError, IndexError):
            continue
            
        coordinates.extend(edge_coords)
    
    # Convert to Folium's [lat, lon] format
    folium.PolyLine(
        locations=[[lat, lon] for lon, lat in coordinates],
        weight=5,
        color='red',
        opacity=0.8
    ).add_to(m)

    folium.Marker(
        [G.nodes[route[0]]['y'], G.nodes[route[0]]['x']],
        popup='Start',
        icon=folium.Icon(color='green')
    ).add_to(m)
    
    folium.Marker(
        [G.nodes[route[-1]]['y'], G.nodes[route[-1]]['x']],
        popup='End',
        icon=folium.Icon(color='red')
    ).add_to(m)
    
    return m

def optimize_route(G, start_node, end_node):
    current_hour = datetime.now().hour
    
    for u, v, k, data in G.edges(data=True, keys=True):
        road_type = data.get('highway', 'unclassified')
        data['weight'] = get_traffic_weight(road_type, current_hour)
    
    try:
        return nx.shortest_path(G, start_node, end_node, weight='weight')
    except nx.NetworkXNoPath:
        return None

def main():
    st.title("🚗 Smart Traffic Router - Bengaluru")
    city = "Bengaluru, India"
    
    with st.spinner("Loading city map data..."):
        try:
            G = load_city_graph(city)
        except Exception as e:
            st.error(f"Error loading map data: {str(e)}")
            return

    col1, col2 = st.columns(2)
    with col1:
        start = st.text_input("Start location", "Indiranagar, Bengaluru")
    with col2:
        end = st.text_input("End location", "Koramangala, Bengaluru")

    if st.button("Find Optimal Route", type="primary"):
        with st.spinner("Calculating your route..."):
            try:
                start_coords = cached_geocode(start)
                end_coords = cached_geocode(end)
                start_node = ox.distance.nearest_nodes(G, start_coords[1], start_coords[0])
                end_node = ox.distance.nearest_nodes(G, end_coords[1], end_coords[0])
                route = optimize_route(G, start_node, end_node)
                
                if route:
                    m = plot_route_on_map(G, route)
                    folium_static(m)
                    st.success("✅ Route found successfully!")
                else:
                    st.error("❌ No valid route found between these locations")
                    
            except Exception as e:
                st.error(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
