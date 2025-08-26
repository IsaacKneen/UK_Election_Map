import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium

# --- Data Configuration ---
# This dictionary holds the specific information for each election year.
# It now includes the column names for both the constituency name and the unique ONS code.
# Updated ELECTION_DATA with direct ONS Geoportal URLs
ELECTION_DATA = {
    '2024': {
        'geojson_url': "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/Westminster_Parliamentary_Constituencies_July_2024_Boundaries_UK_BUC/FeatureServer/0/query?outFields=*&where=1%3D1&f=geojson",
        'results_file': 'HoC-GE2024-results-by-constituency.csv',
        'geo_name_col': 'PCON24NM', # GeoJSON constituency name column
        'geo_code_col': 'PCON24CD'  # GeoJSON constituency code column
    },
    '2019': {
        # 2019 boundaries from ONS Geoportal
        'geojson_url': "https://opendata.arcgis.com/api/v3/datasets/b611e223cb4a4e0ea12b87ac46d03810_0/downloads/data?format=geojson&spatialRefId=4326",
        'results_file': 'HoC-GE2019-results-by-constituency.csv',
        'geo_name_col': 'pcon19nm',
        'geo_code_col': 'pcon19cd'
    },
    '2017': {
        # Use 2019 boundaries for 2017
        'geojson_url': "https://opendata.arcgis.com/api/v3/datasets/b611e223cb4a4e0ea12b87ac46d03810_0/downloads/data?format=geojson&spatialRefId=4326",
        'results_file': 'HoC-GE2017-results-by-constituency.csv',
        'geo_name_col': 'pcon19nm',
        'geo_code_col': 'pcon19cd'
    },
    '2015': {
        # Use 2019 boundaries for 2015
        'geojson_url': "https://opendata.arcgis.com/api/v3/datasets/b611e223cb4a4e0ea12b87ac46d03810_0/downloads/data?format=geojson&spatialRefId=4326",
        'results_file': 'HoC-GE2015-results-by-constituency.csv',
        'geo_name_col': 'pcon19nm',
        'geo_code_col': 'pcon19cd'
    },
    '2010': {
        # Use 2019 boundaries for 2010
        'geojson_url': "https://opendata.arcgis.com/api/v3/datasets/b611e223cb4a4e0ea12b87ac46d03810_0/downloads/data?format=geojson&spatialRefId=4326",
        'results_file': 'HoC-GE2010-results-by-constituency.csv',
        'geo_name_col': 'pcon19nm',
        'geo_code_col': 'pcon19cd'
    }
}

# Use Streamlit's caching to avoid re-loading data on every interaction
@st.cache_data
def load_data(year):
    """
    Loads constituency boundaries and election results for a specific year.
    This function is cached to improve performance.
    """
    config = ELECTION_DATA[year]
    
    st.info(f"Downloading {year} constituency boundaries...")
    try:
        constituencies_gdf = gpd.read_file(config['geojson_url'])
    except Exception as e:
        st.error(f"Failed to download or read the GeoJSON file for {year}: {e}")
        return None, None

    st.info(f"Loading local {year} election results...")
    try:
        results_df = pd.read_csv(config['results_file'])
        
        # Handle missing columns in older datasets
        if 'Of which other winner' not in results_df.columns:
            results_df['Of which other winner'] = 0  # Add missing column with default value
            
        # Handle UUP column name variation in 2010
        if 'UUP (as UCUNF)' in results_df.columns:
            results_df = results_df.rename(columns={'UUP (as UCUNF)': 'UUP'})
            
    except FileNotFoundError:
        st.error(f"Error: The file '{config['results_file']}' was not found.")
        st.warning(f"Please ensure the results file for {year} is in the same folder as this script.")
        return None, None
    except Exception as e:
        st.error(f"Failed to read or parse the local CSV file for {year}: {e}")
        return None, None
        
    return constituencies_gdf, results_df

def create_election_map_app():
    """
    Creates the Streamlit application for the UK election map.
    """
    st.set_page_config(page_title="UK Election Map", layout="wide")
    st.title("Interactive UK General Election Map")

    # --- Sidebar for Year Selection ---
    st.sidebar.title("Options")
    selected_year = st.sidebar.selectbox(
        "Select General Election Year",
        options=list(ELECTION_DATA.keys()),
        index=0 # Default to 2024
    )
    
    st.header(f"Results for {selected_year}")
    st.write("Hover over a constituency to see the winning candidate and party.")

    constituencies_gdf, results_df = load_data(selected_year)

    if constituencies_gdf is None or results_df is None:
        st.warning("Could not load all data. The map cannot be displayed.")
        return

    # --- Data Cleaning and Preparation ---
    config = ELECTION_DATA[selected_year]
    geo_name_col = config['geo_name_col']
    geo_code_col = config['geo_code_col']
    
    # Standardize column names from the results CSV for merging
    results_df.rename(columns={
        'ONS ID': 'ons_id', # Use the ONS ID for merging
        'First party': 'party_name',
        'Member first name': 'firstname',
        'Member surname': 'surname',
        'Majority': 'votes'
    }, inplace=True)

    # Merge using the unique ONS code for a reliable join
    merged_gdf = constituencies_gdf.merge(
        results_df, 
        left_on=geo_code_col, 
        right_on='ons_id', 
        how='left'
    )
    
    # --- FIX: Dynamic Party Color Mapping ---
    # Master dictionary of all known party colors, including historical ones.
    master_party_colors = {
        'Lab': '#E4003B', 'Con': '#0087DC', 'LD': '#FAA61A',
        'SNP': '#FDF000', 'Reform': '#12B6CF', 'Green': '#6AB023',
        'PC': '#008142', 'DUP': '#D46A4C', 'SF': '#326760',
        'Alliance': '#F6CB2F', 'Speaker': '#808080', 'Others': '#808080',
        'UKIP': '#70147A', # UK Independence Party
        'BRX': '#12B6CF',  # Brexit Party (uses Reform's color for consistency)
        'KHHC': '#008080'  # Kidderminster Hospital and Health Concern
    }
    
    # Fill any constituencies that didn't have a match with a default party name
    merged_gdf['party_name'].fillna('Others', inplace=True)
    
    # Apply colors using the master dictionary, with a default for any unknown parties
    merged_gdf['color'] = merged_gdf['party_name'].apply(
        lambda x: master_party_colors.get(x, master_party_colors['Others'])
    )

    # --- Map Creation ---
    m = folium.Map(location=[54.5, -2.5], zoom_start=6)

    geojson_layer = folium.GeoJson(
        merged_gdf,
        style_function=lambda feature: {
            'fillColor': feature['properties']['color'],
            'color': 'black',
            'weight': 0.5,
            'fillOpacity': 0.7,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=[geo_name_col, 'party_name', 'firstname', 'surname', 'votes'],
            aliases=['Constituency:', 'Winning Party:', 'First Name:', 'Surname:', 'Majority Votes:'],
            localize=True
        )
    )
    geojson_layer.add_to(m)

    # Display the map in the Streamlit app
    st_folium(m, width='100%', height=600)

if __name__ == '__main__':
    create_election_map_app()