#---------THE BELOW CODE SUCCESSFUL CAPTURES INVENTORY INPUT, GPS LOCATION, QR CODE, SNAPSHOT---------
#---------With all facilities + header + proper field reset after Add Stock-----------------
#---------Multiple User facility working and Visible for management in admin section--------

import streamlit as st
import pandas as pd
import os
import sqlite3
import hashlib
import base64
from datetime import date, datetime
from pathlib import Path
import streamlit.components.v1 as components

# ---------- Page config (keep at very top) ----------
st.set_page_config(page_title="Kalpadeep IMS", layout="wide")

# ---------- Paths ----------
BASE_DIR = Path(__file__).resolve().parent
DB_FILE = str(BASE_DIR / "inventory.db")
MASTER_FILE = str(BASE_DIR / "Item_master.xlsx")

# ---------- Debug / Dev Mode ----------
DEBUG_MODE = False  # Change to True to see insert debug info


# ---------- Images / Header ----------
def img_to_base64(path: Path):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return None


def render_public_header():
    company_logo_path = BASE_DIR / "Kalpadeep Logo.jpg"
    fabrication_logo_path = BASE_DIR / "Fabrication Logo.jpg"

    col1, col2, col3 = st.columns([1.5, 2, 1.5], vertical_alignment="center")

    with col1:
        if fabrication_logo_path.exists():
            st.image(str(fabrication_logo_path), width=100)

    with col2:
        st.markdown(
            """
            <div style='text-align:center;
                        font-size:17px;
                        font-weight:400;
                        margin:0;'>
                KALPADEEP INDUSTRIES PVT LTD
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            """
            <div style='text-align:center;
                        color:#B87333;
                        font-size:15px;
                        font-weight:400;
                        letter-spacing:1.0px;
                        margin-top:6px;'>
                Inventory Management System
            </div>
            """,
            unsafe_allow_html=True
        )

    with col3:
        if company_logo_path.exists():
            st.image(str(company_logo_path), width=100)

    st.divider()

def render_sidebar_header():
    company_logo_path = BASE_DIR / "Kalpadeep Logo.jpg"
    if company_logo_path.exists():
        st.sidebar.image(str(company_logo_path), use_container_width=True)
    st.sidebar.markdown("**KALPADEEP INDUSTRIES PVT LTD**")
    st.sidebar.caption("Inventory Management System")
    st.sidebar.markdown("---")


# ---------- Multi level Authentication ----------
def check_login(username, password):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    hashed_password = hashlib.sha256(password.encode()).hexdigest()

    cursor.execute("""
        SELECT role, must_change_password
        FROM users
        WHERE username = ? AND password = ?
    """, (username, hashed_password))

    result = cursor.fetchone()
    conn.close()

    if result:
        return {
            "success": True,
            "role": result[0],
            "must_change_password": result[1]
        }

    return {"success": False}


def initialize_users_table():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT,
        must_change_password INTEGER DEFAULT 1
    )
    """)

    # Create default admin if not exists
    admin_password = hashlib.sha256("admin123".encode()).hexdigest()

    cursor.execute("SELECT * FROM users WHERE username = ?", ("admin",))
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO users (username, password, role, must_change_password)
            VALUES (?, ?, ?, ?)
        """, ("admin", admin_password, "admin", 0))

    conn.commit()
    conn.close()


def initialize_database_safe():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_master_id TEXT,
            item_description TEXT,
            grade_name TEXT,
            group1_name TEXT,
            group2_name TEXT,
            section_name TEXT,
            unit_weight REAL,
            source TEXT,
            vendor_name TEXT,
            make TEXT,
            vehicle_number TEXT,
            invoice_date TEXT,
            project_name TEXT,
            thickness REAL,
            length REAL,
            width REAL,
            qr_code TEXT,
            snapshot TEXT,
            latitude REAL,
            longitude REAL,
            rack INTEGER,
            shelf INTEGER,
            quantity REAL,
            price REAL,
            stock_date TEXT,
            added_by TEXT
        )
    """)

    conn.commit()
    conn.close()


def clean_value(val):
    if pd.isna(val):
        return None
    return val


# Ensure tables exist
initialize_users_table()
initialize_database_safe()


def append_stock(selected_row, source, vendor_name, make,
                 vehicle_number, invoice_date, project_name,
                 thickness, length, width,
                 qr_code, snapshot_path,
                 latitude, longitude,
                 rack, shelf,
                 quantity, price, stock_date,
                 added_by):

    if not added_by:
        added_by = ""

    # Convert numpy types to Python native types
    def to_native(val):
        import numpy as np
        if isinstance(val, (np.integer,)):
            return int(val)
        if isinstance(val, (np.floating,)):
            return float(val)
        return val

    insert_values = (
        to_native(selected_row["Item Master ID"]),
        to_native(selected_row["Item Description"]),
        to_native(selected_row["Grade Name"]),
        to_native(selected_row["Group1 Name"]),
        to_native(selected_row["Group2 Name"]),
        to_native(selected_row["Section Name"]),
        to_native(selected_row["Unit Wt. (kg/m)"]),
        to_native(source),
        to_native(vendor_name),
        to_native(make),
        to_native(vehicle_number),
        str(invoice_date) if invoice_date else None,
        to_native(project_name),
        to_native(thickness) if thickness is not None else None,
        to_native(length) if length is not None else None,
        to_native(width) if width is not None else None,
        to_native(qr_code) if qr_code else None,
        to_native(snapshot_path) if snapshot_path else None,
        to_native(latitude) if latitude is not None else None,
        to_native(longitude) if longitude is not None else None,
        to_native(rack) if rack is not None else None,
        to_native(shelf) if shelf is not None else None,
        to_native(quantity) if quantity is not None else None,
        to_native(price) if price is not None else None,
        str(stock_date) if stock_date else None,
        to_native(added_by) if added_by else ""
    )

    if DEBUG_MODE:
        st.write("DEBUG INSERT VALUES:", insert_values)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO inventory (
            item_master_id,
            item_description,
            grade_name,
            group1_name,
            group2_name,
            section_name,
            unit_weight,
            source,
            vendor_name,
            make,
            vehicle_number,
            invoice_date,
            project_name,
            thickness,
            length,
            width,
            qr_code,
            snapshot,
            latitude,
            longitude,
            rack,
            shelf,
            quantity,
            price,
            stock_date,
            added_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, insert_values)
    conn.commit()
    conn.close()


def load_master_data():
    df = pd.read_excel(MASTER_FILE)
    df.columns = df.columns.str.strip()
    return df


def load_stock_data():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM inventory", conn)
    conn.close()
    if not df.empty:
        df["total_value"] = df["quantity"] * df["price"]
    return df


def delete_stock_row(row_id, username, role):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM inventory
        WHERE id = ?
        AND (added_by = ? OR ? = 'admin')
    """, (row_id, username, role))
    conn.commit()
    conn.close()


# ---------- Reset fields after Add Stock ----------
def reset_entry_fields():
    st.session_state["vendor_name"] = ""
    st.session_state["make"] = ""
    st.session_state["vehicle_number"] = ""
    st.session_state["project_name"] = ""

    st.session_state["thickness"] = None
    st.session_state["length"] = None
    st.session_state["width"] = None

    st.session_state["rack"] = None
    st.session_state["shelf"] = None

    st.session_state["quantity"] = None
    st.session_state["price"] = None

    st.session_state["source"] = "Spare RM"
    st.session_state["stock_date"] = date.today()
    st.session_state["invoice_date"] = date.today()

    # IMPORTANT: do NOT pop widget keys; set values instead
    st.session_state["qr_value"] = ""
    st.session_state["gps_value"] = ""


# ---------- SESSION STATE DEFAULTS ----------
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if "stock_added" not in st.session_state:
    st.session_state["stock_added"] = False

# default widget keys (so reset works even first time)
st.session_state.setdefault("qr_value", "")
st.session_state.setdefault("gps_value", "")
st.session_state.setdefault("vendor_name", "")
st.session_state.setdefault("make", "")
st.session_state.setdefault("vehicle_number", "")
st.session_state.setdefault("project_name", "")
st.session_state.setdefault("source", "Spare RM")
st.session_state.setdefault("stock_date", date.today())
st.session_state.setdefault("invoice_date", date.today())
st.session_state.setdefault("thickness", None)
st.session_state.setdefault("length", None)
st.session_state.setdefault("width", None)
st.session_state.setdefault("rack", None)
st.session_state.setdefault("shelf", None)
st.session_state.setdefault("quantity", None)
st.session_state.setdefault("price", None)

# ---------- COMPANY HEADER (SHOW ALWAYS, EVEN BEFORE LOGIN) ----------
render_public_header()

# ---------- Login ----------
if not st.session_state["logged_in"]:
   # st.title("🔐 Login Required")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        result = check_login(username, password)
        if result["success"]:
            st.session_state["logged_in"] = True
            st.session_state["username"] = username
            st.session_state["role"] = result["role"]
            st.session_state["must_change_password"] = result["must_change_password"]
            st.rerun()
        else:
            st.error("Invalid Username or Password")

    st.stop()

# show sidebar header after login
render_sidebar_header()

# ---------- Force Password Change ----------
if st.session_state.get("must_change_password") == 1:
    st.title("🔑 Change Default Password")
    new_password = st.text_input("New Password", type="password")

    if st.button("Update Password"):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        hashed = hashlib.sha256(new_password.encode()).hexdigest()
        cursor.execute("""
            UPDATE users
            SET password = ?, must_change_password = 0
            WHERE username = ?
        """, (hashed, st.session_state["username"]))
        conn.commit()
        conn.close()

        st.session_state["must_change_password"] = 0
        st.success("Password updated successfully!")
        st.rerun()

    st.stop()

# ---------- Logout ----------
col1, col2 = st.columns([6, 1])
with col2:
    if st.button("🚪 Logout"):
        st.session_state.clear()
        st.rerun()

# ---------- Admin Panel ----------
if st.session_state.get("role") == "admin":
    st.sidebar.markdown("### 👨‍💼 Admin Panel")

    with st.sidebar.form("create_user_form", clear_on_submit=True):
        new_user = st.text_input("New Username", key="new_user_name")
        submitted = st.form_submit_button("Create User")

    if submitted:
        if not new_user.strip():
            st.sidebar.error("Username cannot be empty")
        else:
            default_password = hashlib.sha256("123456".encode()).hexdigest()
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO users (username, password, role, must_change_password)
                    VALUES (?, ?, ?, ?)
                """, (new_user.strip(), default_password, "user", 1))
                conn.commit()
                st.sidebar.success("User created! Default password: 123456")
            except sqlite3.IntegrityError:
                st.sidebar.error("User already exists")
            finally:
                conn.close()

            st.session_state["new_user_name"] = ""
            st.rerun()

    st.sidebar.markdown("---")

    st.subheader("👤 User Management")
    conn = sqlite3.connect(DB_FILE)
    user_df = pd.read_sql_query("SELECT id, username, role FROM users ORDER BY id", conn)
    conn.close()

    if user_df.empty:
        st.info("No users found.")
    else:
        st.dataframe(user_df, use_container_width=True)

        selected_user = st.selectbox("Select User", user_df["username"], key="selected_user")

        c1, c2 = st.columns(2)

        with c1:
            if st.button("🔑 Reset Password", key="btn_reset_password"):
                default_password = hashlib.sha256("123456".encode()).hexdigest()
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE users
                    SET password = ?, must_change_password = 1
                    WHERE username = ?
                """, (default_password, selected_user))
                conn.commit()
                conn.close()
                st.success("Password reset to default (123456).")
                st.rerun()

        with c2:
            if st.button("❌ Delete User", key="btn_delete_user"):
                if selected_user == "admin":
                    st.error("Admin account cannot be deleted.")
                elif selected_user == st.session_state.get("username"):
                    st.error("You cannot delete yourself.")
                else:
                    conn = sqlite3.connect(DB_FILE)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM users WHERE username = ?", (selected_user,))
                    conn.commit()
                    conn.close()
                    st.success("User deleted successfully.")
                    st.rerun()


# ---------- Main Stock Entry UI ----------
master_df = load_master_data()

# 1️⃣ Select Category
categories = sorted(master_df["Group2 Name"].dropna().unique())
selected_category = st.selectbox("Select Category", categories)

filtered_category = master_df[master_df["Group2 Name"] == selected_category]

# 2️⃣ Select Grade
grades = sorted(filtered_category["Grade Name"].dropna().unique())
selected_grade = st.selectbox("Select Grade", grades)

filtered_grade = filtered_category[filtered_category["Grade Name"] == selected_grade]

# 3️⃣ Select Item
selected_item_index = st.selectbox(
    "Select Item",
    filtered_grade.index,
    format_func=lambda x: filtered_grade.loc[x, "Item Description"]
)

selected_row = filtered_grade.loc[selected_item_index]

# ---------- Dimension Fields (WITH KEYS so they can reset) ----------
thickness = st.number_input("Thickness (mm)", value=None, placeholder="Enter thickness", key="thickness")
length = st.number_input("Length (Meters)", value=None, placeholder="Enter length", key="length")
width = st.number_input("Width (Meters)", value=None, placeholder="Enter width", key="width")

# ---------- QR SCANNER ----------
st.markdown("### 📷 Scan QR Code")
st.text_input("qr_value", key="qr_value", label_visibility="collapsed")

qr_html = """
<script src="https://unpkg.com/html5-qrcode"></script>
<div id="reader" style="width:300px;"></div>
<script>
function onScanSuccess(decodedText) {
    const streamlitDoc = window.parent.document;
    const input = streamlitDoc.querySelector('input[aria-label="qr_value"]');
    if (input){
        input.value = decodedText;
        input.dispatchEvent(new Event('input', { bubbles: true }));
    }
}
let html5QrcodeScanner = new Html5QrcodeScanner(
    "reader",
    {
        fps: 10,
        qrbox: 250,
        supportedScanTypes: [Html5QrcodeScanType.SCAN_TYPE_CAMERA],
        videoConstraints: { facingMode: { exact: "environment" } }
    }
);
html5QrcodeScanner.render(onScanSuccess);
</script>
"""
components.html(qr_html, height=400)

# ---------- GPS ----------
st.markdown("### 📍 Auto GPS Location")
st.text_input("gps_value", key="gps_value", label_visibility="collapsed")

gps_html = """
<script>
function getLocation() {
    if (!navigator.geolocation) {
        alert("Geolocation is not supported by this browser.");
        return;
    }
    navigator.geolocation.getCurrentPosition(
        function(position) {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;
            const loc = lat + "," + lon;

            const streamlitDoc = window.parent.document;
            const input = streamlitDoc.querySelector('input[aria-label="gps_value"]');

            if (input){
                input.value = loc;
                input.dispatchEvent(new Event('input', { bubbles: true }));
            }
            alert("Location Captured Successfully");
        },
        function(error) {
            alert("Error capturing location: " + error.message);
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
}
</script>

<button onclick="getLocation()" style="
padding:10px 14px;
background-color:#007BFF;
color:white;
border:none;
border-radius:6px;
font-size:16px;">
📍 Capture GPS Location
</button>
"""
components.html(gps_html, height=90)

gps_value = st.session_state.get("gps_value")
if gps_value and "," in gps_value:
    latitude, longitude = map(float, gps_value.split(","))
    st.success(f"📍 Location: {latitude}, {longitude}")
else:
    latitude, longitude = None, None

# ---------- Rack & Shelf (WITH KEYS) ----------
rack = st.number_input("Rack Number", value=None, placeholder="Enter Rack Number", key="rack")
shelf = st.number_input("Shelf Number", value=None, placeholder="Enter Shelf Number", key="shelf")

# Display item details
st.write("**Item Details:**")
st.write({
    "Item Master ID": selected_row["Item Master ID"],
    "Description": selected_row["Item Description"],
    "Grade": selected_row["Grade Name"],
    "Unit Weight (kg/m)": selected_row["Unit Wt. (kg/m)"]
})

# Dates (WITH KEYS)
stock_date = st.date_input("📅 Select Stock Entry Date", key="stock_date")

# Inputs (WITH KEYS)
vendor_name = st.text_input("Vendor Name", key="vendor_name")
make = st.text_input("Make", key="make")
vehicle_number = st.text_input("Vehicle Number", key="vehicle_number")
invoice_date = st.date_input("📅 Select Invoice Date", key="invoice_date")
project_name = st.text_input("Project Name", key="project_name")

source = st.selectbox("Select Source", ["Spare RM", "Project Inventory", "Off-Cut"], key="source")
quantity = st.number_input("Enter Quantity", value=None, placeholder="Enter Quantity in Numbers", key="quantity")
price = st.number_input("Enter Price per unit", value=None, placeholder="Enter Price", key="price")

st.markdown("### 📸 Item Snapshot (Optional)")
snapshot = st.camera_input("Take Snapshot")

# ---------- Add stock ----------
if st.button("➕ Add Stock"):
    if quantity is None or price is None or quantity <= 0 or price <= 0:
        st.error("❌ Quantity and Price must be greater than 0")
    else:
        # Clean selected_row values
        for col in ["Item Master ID", "Item Description", "Grade Name",
                    "Group1 Name", "Group2 Name", "Section Name", "Unit Wt. (kg/m)"]:
            selected_row[col] = clean_value(selected_row[col])

        qr_code = st.session_state.get("qr_value", "")

        # Save snapshot
        snapshot_path = None
        if snapshot:
            (BASE_DIR / "images").mkdir(exist_ok=True)
            safe_name = (
                qr_code.strip()
                .replace("/", "_").replace("\\", "_")
                .replace(" ", "_").replace(":", "_")
            ) if qr_code else "photo"
            snapshot_path = str(BASE_DIR / "images" / f"{safe_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg")
            with open(snapshot_path, "wb") as f:
                f.write(snapshot.getbuffer())

        try:
            append_stock(
                selected_row, source, vendor_name, make,
                vehicle_number, invoice_date, project_name,
                thickness, length, width,
                qr_code, snapshot_path,
                latitude, longitude,
                rack, shelf,
                quantity, price, stock_date,
                st.session_state.get("username")
            )

            st.success("✅ Stock entry successful!")
            st.session_state["stock_added"] = True

            # reset all fields for fresh entry
            reset_entry_fields()
            st.rerun()

        except Exception as e:
            st.error(f"❌ Failed to add stock: {e}")
            import traceback
            st.error(traceback.format_exc())

# ---------- Current Stock ----------
stock_df = load_stock_data()
st.subheader("📊 Current Stock")

if not stock_df.empty:
    st.dataframe(stock_df, use_container_width=True)

    # Single Row Delete (VISIBLE TO ALL)
    st.subheader("🗑 Delete Single Stock Entry")
    row_to_delete = st.selectbox("Select ID to Delete", stock_df["id"])

    if st.button("Delete Selected Entry"):
        delete_stock_row(
            row_to_delete,
            st.session_state.get("username"),
            st.session_state.get("role")
        )
        st.success("✅ Entry deleted successfully")
        st.rerun()

    # Bulk Delete (ADMIN ONLY)
    if st.session_state.get("role") == "admin":
        st.markdown("### 🚨 Bulk Delete (Admin Only)")
        min_id = int(stock_df["id"].min())
        max_id = int(stock_df["id"].max())

        c1, c2 = st.columns(2)
        with c1:
            start_id = st.number_input("From ID", min_value=min_id, max_value=max_id)
        with c2:
            end_id = st.number_input("To ID", min_value=min_id, max_value=max_id)

        if st.button("Delete Range"):
            if start_id > end_id:
                st.error("Start ID cannot be greater than End ID")
            else:
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM inventory WHERE id BETWEEN ? AND ?", (start_id, end_id))
                conn.commit()
                conn.close()
                st.success(f"✅ Deleted records from ID {start_id} to {end_id}")
                st.rerun()
else:
    st.info("No stock entries available.")
