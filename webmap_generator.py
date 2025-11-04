# ============================================================
# webmap_generator.py (no ZIP, satellite only, no opacity slider)
# ============================================================

import geopandas as gpd
import folium, tempfile, requests, gdown, re, json, base64
from shapely.geometry import Polygon, MultiPolygon

# -------------------- Download tools --------------------
def extract_drive_id(url: str):
    m = re.search(r"/file/d/([^/]+)/", url)
    if m: return m.group(1)
    m = re.search(r"[?&]id=([^&]+)", url)
    if m: return m.group(1)
    return ""

def download_any(url: str, suffix=".dat"):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.close()
    if "drive.google.com" in url:
        fid = extract_drive_id(url)
        gdown.download(id=fid, output=tmp.name, quiet=True)
    else:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        with open(tmp.name, "wb") as f:
            f.write(r.content)
    return tmp.name

# -------------------- CRS tools --------------------
def ensure_wgs84(gdf):
    if gdf.crs is None:
        return gdf.set_crs(epsg=4326)
    else:
        return gdf.to_crs(epsg=4326)

# -------------------- ICON tools --------------------
def drive_to_direct(url_or_id: str, size_px: int = 48) -> str:
    if re.fullmatch(r"[A-Za-z0-9_-]{20,}", url_or_id):
        fid = url_or_id
    else:
        fid = extract_drive_id(url_or_id) or url_or_id
    return f"https://drive.google.com/thumbnail?id={fid}&sz=w{size_px}"

def url_to_data_uri(url: str) -> str:
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    content = r.content
    mime = "image/png"
    if content[:3] == b'\xff\xd8\xff': mime = "image/jpeg"
    elif content[:4] == b'\x89PNG':    mime = "image/png"
    elif content[:3] == b'GIF':        mime = "image/gif"
    b64 = base64.b64encode(content).decode("ascii")
    return f"data:{mime};base64,{b64}"

def normalize_text(s: str) -> str:
    return str(s).strip().casefold()

def icon_for_feature(props, icon_rules):
    field = icon_rules.get("field")
    mapping = icon_rules.get("mapping", {})
    default = icon_rules.get("default", {"icon":"map-marker","prefix":"fa"})

    if not field or field not in props:
        return default

    val = normalize_text(props.get(field, ""))
    norm_exact = {normalize_text(k): v for k, v in mapping.items()}

    if val in norm_exact:
        return norm_exact[val]

    for k_raw, rule in mapping.items():
        if k_raw.endswith("*"):
            if val.startswith(normalize_text(k_raw[:-1])):
                return rule

    return default

# -------------------- Popup & Marker --------------------
def all_fields_popup_html(props: dict) -> str:
    rows = []
    for k, v in props.items():
        if k == "geometry": continue
        if isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False)
        rows.append(f"<tr><th style='text-align:left;padding:2px 6px;'>{k}</th><td style='padding:2px 6px;'>{v}</td></tr>")
    return "<table>" + "".join(rows) + "</table>"

def add_points_markers(target_layer, selected_gdf, icon_rules, icon_size_default=(28,28), embed_icons=True):
    for _, row in selected_gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty or geom.geom_type != "Point":
            continue
        lat, lon = geom.y, geom.x
        props = row.drop(labels=["geometry"]).to_dict()
        rule = icon_for_feature(props, icon_rules)
        popup_html = all_fields_popup_html(props)

        if "icon_url" in rule:
            icon_url = rule["icon_url"]
            if "drive.google.com" in icon_url or re.fullmatch(r"[A-Za-z0-9_-]{20,}", icon_url):
                sz = rule.get("icon_size", list(icon_size_default))
                px = max(sz) if isinstance(sz, (list, tuple)) else max(icon_size_default)
                direct = drive_to_direct(icon_url, size_px=px)
            else:
                direct = icon_url

            if embed_icons:
                try:
                    icon_src = url_to_data_uri(direct)
                except Exception:
                    icon_src = direct
            else:
                icon_src = direct

            icon = folium.features.CustomIcon(icon_src, icon_size=rule.get("icon_size", list(icon_size_default)))
            folium.Marker([lat, lon], popup=folium.Popup(popup_html, max_width=400), icon=icon).add_to(target_layer)
        else:
            folium.Marker(
                [lat, lon],
                popup=folium.Popup(popup_html, max_width=400),
                icon=folium.Icon(icon=rule.get("icon","map-marker"), prefix=rule.get("prefix","fa"))
            ).add_to(target_layer)

# -------------------- ICON RULES --------------------
DEFAULT_ICON_RULES = {
    "field": "Brand",
    "mapping": {
        "CJ SUPERMARKET + BAO*": {"icon_url": "1kaeronC0Q-h6uHbdKNzm8381m1SIFFZX","icon_size": [28, 28]},
        "CJ*": {"icon_url": "1kaeronC0Q-h6uHbdKNzm8381m1SIFFZX","icon_size": [28, 28]},
        "BigC Extra": {"icon_url": "1iyA4ukSIoz4TX6G6G8PJONV2WglQVSuY","icon_size": [28, 28]},
        "BigC Market": {"icon_url": "1Whmmo2cI95srD20kDZ2xJYoRO_kc_PbM","icon_size": [28, 28]},
        "Lotus Extra": {"icon_url": "1Mj12L7s8hYjCjjjHsewzgcKjZtszper7","icon_size": [28, 28]},
        "Lotus Gofresh": {"icon_url": "1tDZtAjFbYWr_D0FZpcp4ai8JcCNfxkHb","icon_size": [28, 28]},
        "Lotus Market": {"icon_url": "1Mj12L7s8hYjCjjjHsewzgcKjZtszper7","icon_size": [28, 28]},
        "7-Eleven": {"icon_url": "1dpBuOig0swLfqSyVSfUqzZYBptJA390-","icon_size": [28, 28]},
        "Tops": {"icon_url": "13Y68KyDdCwNoTo_dJwkQ3WcjlvM6RqoO","icon_size": [28, 28]},
        "MBC": {"icon_url": "1PQmuQ0hQm2a8KCzLaiQLDtHrh8AOz8sr","icon_size": [28, 28]},
        "ETC.": {"icon_url": "1yDbY2Tjq0kzA2gxrnMSDHvfwS_Ki7flh","icon_size": [28, 28]},
    },
    "default": {"icon":"map-marker","prefix":"fa"}
}

# -------------------- Main Map Generator --------------------
def generate_webmap(kml_url, points_url, site_name, ns_id, icon_rules=None):
    """สร้าง Webmap พื้นหลังดาวเทียมเท่านั้น + LayerControl สำหรับข้อมูล"""
    kml_path = download_any(kml_url, ".kml")
    pts_path = download_any(points_url, ".geojson")

    # โหลดข้อมูล
    kml = gpd.read_file(kml_path, driver="KML")
    pts = gpd.read_file(pts_path)
    kml, pts = ensure_wgs84(kml), ensure_wgs84(pts)

    # รวมขอบเขต
    geom = kml.geometry.unary_union
    selected = pts[pts.within(geom)]

    # ขอบเขตซูม
    minx, miny, maxx, maxy = geom.bounds

    # === แผนที่หลัก (ไม่มี OSM) ===
    m = folium.Map(
        location=[(miny + maxy) / 2, (minx + maxx) / 2],
        zoom_start=10,
        control_scale=True,
        tiles=None
    )

    # === เพิ่มภาพพื้นหลังดาวเทียม (ค่าเริ่มต้น) ===
    satellite_layer = folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery",
        name="Satellite",
        overlay=False
    )
    satellite_layer.add_to(m)

    # === เพิ่มชั้น KML Boundary ===
    kml_layer = folium.GeoJson(
        kml,
        name="KML Boundary",
        style_function=lambda x: {
            "fillColor": "#FF0000",
            "color": "#FF0000",
            "weight": 2,
            "fillOpacity": 0.1
        },
        tooltip=folium.features.GeoJsonTooltip(
            fields=["Name"] if "Name" in kml.columns else None,
            aliases=["ชื่อโพลิกอน:"],
            sticky=True
        )
    )
    kml_layer.add_to(m)

    # === ชั้นเส้นขอบ Outline ===
    outline_layer = folium.GeoJson(
        gpd.GeoSeries([geom], crs="EPSG:4326").__geo_interface__,
        name="Boundary Outline",
        style_function=lambda x: {
            "fillColor": "#00000000",
            "color": "#FF4D4D",
            "weight": 1.5
        }
    )
    outline_layer.add_to(m)

    # === ชั้นหมุดคู่แข่ง ===
    icon_rules = icon_rules or DEFAULT_ICON_RULES
    competitor_layer = folium.FeatureGroup(name="Competitor Points", show=True)
    add_points_markers(competitor_layer, selected, icon_rules, embed_icons=True)
    competitor_layer.add_to(m)

    # === ปรับขอบเขตแผนที่ ===
    m.fit_bounds([[miny, minx], [maxy, maxx]])

    # === Layer Control ===
    folium.LayerControl(collapsed=False, position="topright").add_to(m)

    # === บันทึกไฟล์ ===
    out_html = f"{ns_id}_{site_name}.html".replace(" ", "_")
    m.save(out_html)
    return out_html

