import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium
from shapely.geometry import shape

# -----------------------------
# Data configuration (existing)
# -----------------------------
ELECTION_DATA = {
    '2024': {
        # 2024 PCONs (ONS BUC)
        # Source: ONS Westminster Parliamentary Constituencies (July 2024) Boundaries UK BUC (GeoJSON)
        'geojson_url': "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/Westminster_Parliamentary_Constituencies_July_2024_Boundaries_UK_BUC/FeatureServer/0/query?outFields=*&where=1%3D1&f=geojson",
        'results_file': 'HoC-GE2024-results-by-constituency.csv',
        'geo_name_col': 'PCON24NM',
        'geo_code_col': 'PCON24CD'
    },
    '2019': {
        'geojson_url': "https://opendata.arcgis.com/api/v3/datasets/b611e223cb4a4e0ea12b87ac46d03810_0/downloads/data?format=geojson&spatialRefId=4326",
        'results_file': 'HoC-GE2019-results-by-constituency.csv',
        'geo_name_col': 'pcon19nm',
        'geo_code_col': 'pcon19cd'
    },
    '2017': {
        'geojson_url': "https://opendata.arcgis.com/api/v3/datasets/b611e223cb4a4e0ea12b87ac46d03810_0/downloads/data?format=geojson&spatialRefId=4326",
        'results_file': 'HoC-GE2017-results-by-constituency.csv',
        'geo_name_col': 'pcon19nm',
        'geo_code_col': 'pcon19cd'
    },
    '2015': {
        'geojson_url': "https://opendata.arcgis.com/api/v3/datasets/b611e223cb4a4e0ea12b87ac46d03810_0/downloads/data?format=geojson&spatialRefId=4326",
        'results_file': 'HoC-GE2015-results-by-constituency.csv',
        'geo_name_col': 'pcon19nm',
        'geo_code_col': 'pcon19cd'
    },
    '2010': {
        'geojson_url': "https://opendata.arcgis.com/api/v3/datasets/b611e223cb4a4e0ea12b87ac46d03810_0/downloads/data?format=geojson&spatialRefId=4326",
        'results_file': 'HoC-GE2010-results-by-constituency.csv',
        'geo_name_col': 'pcon19nm',
        'geo_code_col': 'pcon19cd'
    }
}

# -----------------------------
# New: LSOA configuration
# -----------------------------
# LSOAs (Dec 2021, England & Wales) - Super-generalised (BSC) = light for web maps
# Official source (ONS Open Geography Portal)
LSOA_GEOJSON_URL = (
    "https://opendata.arcgis.com/api/v3/datasets/04c65a08ecff4858bffc16e9ca9356f4_0/downloads/data?"
    "format=geojson&spatialRefId=4326"
)
# Typical ID/name fields in this feed:
# LSOA21CD (code), LSOA21NM (name), LAD21CD, LAD21NM, RGN21CD, RGN21NM, etc.


# -----------------------------
# Cached loaders
# -----------------------------
@st.cache_data(show_spinner=False)
def load_constituencies(year: str) -> gpd.GeoDataFrame | None:
    cfg = ELECTION_DATA[year]
    try:
        gdf = gpd.read_file(cfg['geojson_url'])
        # ensure WGS84
        if gdf.crs is None or gdf.crs.to_epsg() != 4326:
            gdf = gdf.set_crs(4326, allow_override=True)
        return gdf
    except Exception as e:
        st.error(f"Failed to load {year} constituency GeoJSON: {e}")
        return None

@st.cache_data(show_spinner=False)
def load_results_csv(year: str) -> pd.DataFrame | None:
    cfg = ELECTION_DATA[year]
    try:
        df = pd.read_csv(cfg['results_file'])
        # Normalise expected columns (matches your original script)
        if 'Of which other winner' not in df.columns:
            df['Of which other winner'] = 0
        if 'UUP (as UCUNF)' in df.columns:
            df = df.rename(columns={'UUP (as UCUNF)': 'UUP'})
        # rename for merge
        df = df.rename(columns={
            'ONS ID': 'ons_id',
            'First party': 'party_name',
            'Member first name': 'firstname',
            'Member surname': 'surname',
            'Majority': 'votes'
        })
        return df
    except FileNotFoundError:
        st.error(f"Missing results CSV for {year}: {cfg['results_file']}")
        return None
    except Exception as e:
        st.error(f"Failed to load results CSV for {year}: {e}")
        return None

@st.cache_data(show_spinner=False)
def load_lsoas() -> gpd.GeoDataFrame | None:
    """
    Load England & Wales LSOAs (Dec 2021) BSC GeoJSON.
    This is ~super-generalised and reasonable for web use.
    """
    try:
        gdf = gpd.read_file(LSOA_GEOJSON_URL)
        if gdf.crs is None or gdf.crs.to_epsg() != 4326:
            gdf = gdf.set_crs(4326, allow_override=True)
        return gdf
    except Exception as e:
        st.error(f"Failed to load LSOA GeoJSON: {e}")
        return None


# -----------------------------
# Election map (your existing)
# -----------------------------
def render_election_map():
    st.header("UK General Election Map")
    st.write("Hover over a constituency to see the winning candidate and party.")

    year = st.sidebar.selectbox(
        "Select General Election Year",
        options=list(ELECTION_DATA.keys()),
        index=0
    )

    gdf = load_constituencies(year)
    df = load_results_csv(year)
    if gdf is None or df is None:
        st.warning("Could not load all data. The map cannot be displayed.")
        return

    cfg = ELECTION_DATA[year]
    geo_name_col = cfg['geo_name_col']
    geo_code_col = cfg['geo_code_col']

    merged = gdf.merge(df, left_on=geo_code_col, right_on='ons_id', how='left')

    # Party colours (as in your original)
    master_party_colors = {
        'Lab': '#E4003B', 'Con': '#0087DC', 'LD': '#FAA61A',
        'SNP': '#FDF000', 'Reform': '#12B6CF', 'Green': '#6AB023',
        'PC': '#008142', 'DUP': '#D46A4C', 'SF': '#326760',
        'Alliance': '#F6CB2F', 'Speaker': '#808080', 'Others': '#808080',
        'UKIP': '#70147A', 'BRX': '#12B6CF', 'KHHC': '#008080'
    }
    merged['party_name'] = merged['party_name'].fillna('Others')
    merged['color'] = merged['party_name'].apply(lambda p: master_party_colors.get(p, '#808080'))

    m = folium.Map(location=[54.5, -2.5], zoom_start=6)
    gj = folium.GeoJson(
        merged,
        style_function=lambda feat: {
            'fillColor': feat['properties']['color'],
            'color': 'black',
            'weight': 0.5,
            'fillOpacity': 0.7,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=[geo_name_col, 'party_name', 'firstname', 'surname', 'votes'],
            aliases=['Constituency:', 'Winning Party:', 'First Name:', 'Surname:', 'Majority Votes:'],
            localize=True
        )
    ).add_to(m)

    st_folium(m, width='100%', height=650)


# -----------------------------
# New: Constituency data view
# -----------------------------
def render_constituency_data():
    st.header("UK Parliamentary Constituency Data")
    st.caption("Click a constituency (2024 boundaries). If in England/Wales, its LSOAs will be drawn inside the boundary.")

    year = '2024'
    cfg = ELECTION_DATA[year]
    geo_name_col = cfg['geo_name_col']
    geo_code_col = cfg['geo_code_col']

    pcon_gdf = load_constituencies(year)
    if pcon_gdf is None or pcon_gdf.empty:
        st.warning("Could not load constituency layer.")
        return

    # Sidebar fallback selector (works even if clicks fail)
    with st.sidebar:
        st.markdown("### Fallback selection")
        chosen_name = st.selectbox(
            "Pick a constituency (fallback if click isn't working)",
            sorted(pcon_gdf[geo_name_col].unique())
        )
        use_fallback = st.button("Load selected constituency")

    # Map to click
    m = folium.Map(location=[54.5, -2.5], zoom_start=6)

    # Add a Popup AND Tooltip so clicks are registered
    tooltip = folium.GeoJsonTooltip(
        fields=[geo_name_col, geo_code_col],
        aliases=["Constituency:", "Code:"],
        sticky=False
    )
    popup = folium.GeoJsonPopup(
        fields=[geo_name_col, geo_code_col],
        aliases=["Constituency:", "Code:"],
        parse_html=False,
        max_width=350
    )

    folium.GeoJson(
        pcon_gdf,
        name="Constituencies (2024)",
        tooltip=tooltip,
        popup=popup,
        highlight_function=lambda f: {"weight": 3, "color": "#666666"}
    ).add_to(m)

    click_info = st_folium(m, height=600, width="100%", key="pcon_map")

    # Try to read clicked feature props
    props = None
    if isinstance(click_info, dict):
        # Newer streamlit-folium sets this on popup/feature click
        if click_info.get("last_object_clicked"):
            loc = click_info["last_object_clicked"]
            props = loc.get("properties") or {}
        # Some versions put it here when popup opens
        if not props and click_info.get("last_active_drawing"):
            lad = click_info["last_active_drawing"]
            props = lad.get("properties") or {}

    # Decide selection: click beats fallback; else fallback if button pressed
    selected_code = None
    selected_name = None

    if props and props.get(geo_code_col):
        selected_code = props.get(geo_code_col)
        selected_name = props.get(geo_name_col)
    elif use_fallback:
        selected_name = chosen_name
        row = pcon_gdf.loc[pcon_gdf[geo_name_col] == chosen_name]
        if not row.empty:
            selected_code = row.iloc[0][geo_code_col]

    st.markdown("---")

    if not selected_code:
        st.info("Tip: click a constituency on the map, or use the fallback selector in the sidebar.")
        return

    st.subheader(f"{selected_name} — {selected_code}")

    sel = pcon_gdf[pcon_gdf[geo_code_col] == selected_code].reset_index(drop=True)
    if sel.empty:
        st.error("Couldn’t find the selected constituency in the dataset.")
        return

    # Load LSOAs (England & Wales only)
    lsoas = load_lsoas()
    if lsoas is None or lsoas.empty:
        st.warning("LSOA layer could not be loaded.")
        return

    # Spatial join: LSOAs intersecting the selected constituency
    try:
        lsoas_in = gpd.sjoin(
            lsoas.reset_index(drop=True),
            sel[[geo_code_col, "geometry"]],
            predicate="intersects",
            how="inner"
        )
    except Exception as e:
        st.error(f"Spatial join failed: {e}")
        return

    if lsoas_in.empty:
        st.warning("No LSOAs found. This likely means the constituency is outside England & Wales.")
        return

    # Focused map
    centroid = sel.geometry.iloc[0].centroid
    cm = folium.Map(location=[centroid.y, centroid.x], zoom_start=10)

    folium.GeoJson(
        sel,
        name="Constituency boundary",
        style_function=lambda f: {'fillOpacity': 0.05, 'color': '#000000', 'weight': 2}
    ).add_to(cm)

    lsoa_fields = [c for c in ['LSOA21CD', 'LSOA21NM'] if c in lsoas_in.columns]
    folium.GeoJson(
        lsoas_in,
        name="LSOAs",
        style_function=lambda f: {'fillOpacity': 0.2, 'color': '#444444', 'weight': 0.6},
        tooltip=folium.GeoJsonTooltip(fields=lsoa_fields, aliases=["LSOA Code:", "LSOA Name:"][:len(lsoa_fields)]),
        popup=folium.GeoJsonPopup(fields=lsoa_fields, aliases=["LSOA Code:", "LSOA Name:"][:len(lsoa_fields)])
    ).add_to(cm)

    folium.LayerControl().add_to(cm)
    st_folium(cm, height=650, width="100%", key="detail_map")

    st.write(f"**LSOAs found:** {len(lsoas_in)}  |  **Geometry:** super-generalised (BSC) © ONS")



# -----------------------------
# App shell
# -----------------------------
def main():
    st.set_page_config(page_title="UK Election & Constituency Data", layout="wide")
    st.title("UK Parliamentary Map Hub")

    # Main menu
    view = st.sidebar.radio(
        "Choose a section",
        options=["UK General Election Map", "UK Parliamentary Constituency Data"],
        index=0
    )

    if view == "UK General Election Map":
        render_election_map()
    else:
        render_constituency_data()


if __name__ == '__main__':
    main()