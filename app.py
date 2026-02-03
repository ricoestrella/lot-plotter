import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
import simplekml
import re

# --- 1. THE PARSER (Reads your specific data format) ---
def parse_technical_description(text):
    """
    Parses text like: "1-2  N. 11° 02' W.  18.50 m."
    Returns a list of dictionaries for the math engine.
    """
    lines = []
    # Regex to find: Direction1, Deg, Min, Direction2, Distance
    # It handles "N.", "N", "°", "'", "m.", "m" variants
    pattern = r"([NS])\.?\s*(\d+)[°\s]+(\d+)['\s]+([EW])\.?.*?(\d+\.\d+)"
    
    matches = re.findall(pattern, text, re.IGNORECASE)
    
    for match in matches:
        d1, deg, mins, d2, dist = match
        # Construct a clean string for the math engine (e.g., "N 11-02 W")
        bearing_clean = f"{d1.upper()} {deg}-{mins} {d2.upper()}"
        lines.append({
            "bearing": bearing_clean,
            "distance": float(dist)
        })
    
    return lines

# --- 2. THE MATH ENGINE ---
def parse_dms(bearing_str):
    # Expects "N 11-02 W"
    parts = bearing_str.split() 
    dms = parts[1].replace("-", " ").split()
    deg = float(dms[0])
    mins = float(dms[1]) if len(dms) > 1 else 0
    decimal_deg = deg + (mins / 60.0)
    
    quadrant = parts[0] + parts[2] 
    if quadrant == 'NE': azimuth = decimal_deg
    elif quadrant == 'SE': azimuth = 180 - decimal_deg
    elif quadrant == 'SW': azimuth = 180 + decimal_deg
    elif quadrant == 'NW': azimuth = 360 - decimal_deg
    return np.radians(azimuth)

def calculate_coords(lines, start_lat=None, start_long=None):
    x, y = [0], [0]
    curr_x, curr_y = 0, 0
    geo_coords = []
    
    # Simple factor for Lat/Long estimation (1 deg ~ 111,320m)
    # This is a rough estimation for visualization if pyproj fails or for speed
    meters_per_deg = 111320.0
    
    if start_lat and start_long:
        geo_coords.append((start_long, start_lat))

    for line in lines:
        azimuth = parse_dms(line['bearing'])
        dist = line['distance']
        
        dx = dist * np.sin(azimuth)
        dy = dist * np.cos(azimuth)
        
        curr_x += dx
        curr_y += dy
        x.append(curr_x)
        y.append(curr_y)
        
        if start_lat and start_long:
            # Approximate conversion for small lots (faster than Proj4 for simple apps)
            d_lat = dy / meters_per_deg
            d_long = dx / (meters_per_deg * np.cos(np.radians(start_lat)))
            
            # Update current global pos
            curr_g_lat = geo_coords[-1][1] + d_lat
            curr_g_long = geo_coords[-1][0] + d_long
            geo_coords.append((curr_g_long, curr_g_lat))

    return x, y, geo_coords

def calculate_area(x, y):
    return 0.5 * np.abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))

def create_kml(geo_coords):
    kml = simplekml.Kml()
    pol = kml.newpolygon(name="Lot Plot", outerboundaryis=geo_coords)
    pol.style.linestyle.color = simplekml.Color.red
    pol.style.linestyle.width = 3
    pol.style.polystyle.color = simplekml.Color.changealphaint(100, simplekml.Color.red)
    kml_file = "lot_plot.kml"
    kml.save(kml_file)
    return kml_file

# --- 3. THE APP UI ---
st.title("📍 Lot Plotter & Google Earth Exporter")

st.markdown("""
**Instructions:**
1. Copy the text from your title (e.g., *1-2 N. 11° 02' W. 18.50 m.*)
2. Paste it below.
3. (Optional) Enter a Reference Point to place it on the real map.
""")

with st.form("input_form"):
    col1, col2 = st.columns(2)
    with col1:
        ref_lat = st.number_input("Reference Latitude (Try: 14.38)", value=14.386, format="%.5f")
    with col2:
        ref_long = st.number_input("Reference Longitude (Try: 120.88)", value=120.880, format="%.5f")
    
    # Default text matches your image for easy testing
    default_text = """
    1-2 N. 11° 02' W. 18.50 m.
    2-3 N. 78° 58' E. 4.36 m.
    3-4 N. 78° 58' E. 11.14 m.
    4-5 S. 11° 05' E. 12.00 m.
    5-6 S. 02° 35' E. 2.21 m.
    6-7 S. 17° 16' W. 2.01 m.
    7-8 S. 34° 54' W. 2.01 m.
    8-9 S. 52° 31' W. 2.01 m.
    9-10 S. 71° 35' W. 2.00 m.
    10-1 S. 79° 02' W. 9.00 m.
    """
    raw_text = st.text_area("Paste Technical Description Here", value=default_text, height=200)
    
    submitted = st.form_submit_button("Generate Plot")

if submitted:
    # 1. Parse
    lines = parse_technical_description(raw_text)
    
    if not lines:
        st.error("Could not find any coordinates. Make sure the format looks like: N. 10° 00' E. 10.00 m.")
    else:
        st.success(f"Successfully read {len(lines)} lines.")
        
        # 2. Calculate
        x, y, geo_coords = calculate_coords(lines, ref_lat, ref_long)
        area = calculate_area(x, y)
        
        # 3. Metrics
        st.metric("Calculated Lot Area", f"{area:.2f} sqm")
        
        # 4. Plot
        fig, ax = plt.subplots(figsize=(5,5))
        ax.plot(x, y, 'o-', color='black', linewidth=2)
        ax.fill(x, y, 'blue', alpha=0.1)
        
        # Add labels
        for i in range(len(lines)):
             mid_x, mid_y = (x[i]+x[i+1])/2, (y[i]+y[i+1])/2
             ax.text(mid_x, mid_y, f"{i+1}", color='red', fontsize=12, fontweight='bold')
             
        ax.set_aspect('equal')
        ax.grid(True, linestyle='--')
        st.pyplot(fig)
        
        # 5. Download KML
        kml_file = create_kml(geo_coords)
        with open(kml_file, "rb") as file:
            st.download_button(
                label="🌍 Download Google Earth File (KML)",
                data=file,
                file_name="my_lot.kml",
                mime="application/vnd.google-earth.kml+xml"
            )
