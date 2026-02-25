

import streamlit as st
import pandas as pd
import os
import sqlite3
import hashlib
import base64
from datetime import date, datetime
from pathlib import Path
import streamlit.components.v1 as components
import numpy as np

# ---------- Page config (keep at very top) ----------
st.set_page_config(page_title="Kalpadeep IMS", layout="wide")

# ---------- Paths ----------
BASE_DIR = Path(__file__).resolve().parent
DB_FILE = str(BASE_DIR / "inventory.db")
MASTER_FILE = str(BASE_DIR / "Item_master.xlsx")
IMAGE_DIR = BASE_DIR / "images"

# Ensure image directory exists
IMAGE_DIR.mkdir(exist_ok=True)

# ---------- Debug / Dev Mode ----------
DEBUG_MODE = False  # Change to True to see insert debug info


# ---------- Database Functions ----------
@st.cache_resource
def get_db_connection():
    """Establishes and returns a database connection."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn

def initialize_users_table():
    """Initializes the users table and creates a default admin user if not exists."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
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

def initialize_inventory_table():
    """Initializes the inventory table."""
    conn = get_db_connection()
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

# Ensure tables exist on app startup
initialize_users_table()
initialize_inventory_table()

def check_login(username, password):
    """Checks user credentials and returns role and password change status."""
    conn = get_db_connection()
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
        return {"success": True, "role": result["role"], "must_change_password": result["must_change_password"]}
    return {"success": False}

def append_stock(data):
    """Appends a new stock entry to the inventory table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    columns = ", ".join(data.keys())
    placeholders = ", ".join(["?"] * len(data))
    query = f"INSERT INTO inventory ({columns}) VALUES ({placeholders})"
    cursor.execute(query, list(data.values()))
    conn.commit()
    conn.close()

def load_master_data():
    """Loads item master data from Excel file."""
    try:
        df = pd.read_excel(MASTER_FILE)
        df.columns = df.columns.str.strip()
        return df
    except FileNotFoundError:
        st.error(f"Error: Master file not found at {MASTER_FILE}")
        return pd.DataFrame()

def load_stock_data():
    """Loads all stock data from the inventory table."""
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM inventory", conn)
    conn.close()
    if not df.empty:
        df["total_value"] = df["quantity"] * df["price"]
    return df

def delete_stock_row(row_id, username, role):
    """Deletes a single stock entry by ID, with admin override."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM inventory
        WHERE id = ?
        AND (added_by = ? OR ? = 'admin')
    """, (row_id, username, role))
    conn.commit()
    conn.close()

def delete_stock_range(start_id, end_id):
    """Deletes a range of stock entries by ID (admin only)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM inventory WHERE id BETWEEN ? AND ?", (start_id, end_id))
    conn.commit()
    conn.close()


# ---------- Helper Functions ----------
def to_native_python_type(val):
    """Converts numpy types to native Python types."""
    if isinstance(val, (np.integer, np.int64)):
        return int(val)
    if isinstance(val, (np.floating, np.float64)):
        return float(val)
    if pd.isna(val):
        return None
    return val

def img_to_base64(path: Path):
    """Converts an image file to a base64 string."""
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return None

def reset_stock_entry_form_state():
    """Resets session state variables related to stock entry form."""
    st.session_state["qr_value"] = ""
    st.session_state["gps_value"] = ""
    st.session_state["vendor_name"] = ""
    st.session_state["make"] = ""
    st.session_state["vehicle_number"] = ""
    st.session_state["project_name"] = ""
    st.session_state["source"] = "Spare RM"
    st.session_state["stock_date"] = date.today()
    st.session_state["invoice_date"] = date.today()
    st.session_state["thickness"] = None
    st.session_state["length"] = None
    st.session_state["width"] = None
    st.session_state["rack"] = None
    st.session_state["shelf"] = None
    st.session_state["quantity"] = None
    st.session_state["price"] = None
    st.session_state["entry_cycle"] += 1 # Increment to force re-render QR/GPS widgets


# ---------- UI Components ----------
def render_public_header():
    """Renders the public header for the application."""
    company_logo_path = BASE_DIR / "Kalpadeep Logo.jpg"
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if company_logo_path.exists():
            st.image(str(company_logo_path), width=200)
        st.markdown(
            """
            <div style='text-align:left;
                        font-size:22px;
                        font-weight:700;
                        margin-top:4px;'>
                KALPADEEP INDUSTRIES PVT LTD
            </div>
            """,
            unsafe_allow_html=True
        )
        st.markdown(
            """
            <div style='text-align:left;
                        color:#B87333;
                        font-size:18px;
                        font-weight:500;
                        letter-spacing:1px;
                        margin-top:4px;'>
                Inventory Management System
            </div>
            """,
            unsafe_allow_html=True
        )
    st.divider()

def render_sidebar_header():
    """Renders the sidebar header with company logo and name."""
    company_logo_path = BASE_DIR / "Kalpadeep Logo.jpg"
    if company_logo_path.exists():
        st.sidebar.image(str(company_logo_path), use_container_width=True)
    st.sidebar.markdown("**KALPADEEP INDUSTRIES PVT LTD**")
    st.sidebar.caption("Inventory Management System")
    st.sidebar.markdown("---")


def render_login_form():
    """Renders the login form."""
    st.subheader("Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            login_result = check_login(username, password)
            if login_result["success"]:
                st.session_state["logged_in"] = True
                st.session_state["username"] = username
                st.session_state["role"] = login_result["role"]
                st.session_state["must_change_password"] = login_result["must_change_password"]
                st.rerun()
            else:
                st.error("Invalid username or password")

def render_change_password_form():
    """Renders the change password form for new users."""
    st.subheader("Change Password")
    with st.form("change_password_form"):
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm New Password", type="password")
        submitted = st.form_submit_button("Change Password")
        if submitted:
            if new_password == confirm_password:
                conn = get_db_connection()
                cursor = conn.cursor()
                hashed_password = hashlib.sha256(new_password.encode()).hexdigest()
                cursor.execute("""
                    UPDATE users SET password = ?, must_change_password = 0 WHERE username = ?
                """, (hashed_password, st.session_state["username"]))
                conn.commit()
                conn.close()
                st.session_state["must_change_password"] = 0
                st.success("Password changed successfully!")
                st.rerun()
            else:
                st.error("New password and confirm password do not match.")

def render_qr_scanner():
    """Renders the QR code scanner component."""
    cycle = st.session_state["entry_cycle"]
    reader_id = f"reader_{cycle}"
    qr_html = f"""
    <script src="https://unpkg.com/html5-qrcode"></script>
    <div id="{reader_id}" style="width:300px;"></div>
    <script>
    (function() {{
        const el = document.getElementById("{reader_id}");
        if(!el) return;
        function onScanSuccess(decodedText) {{
            const streamlitDoc = window.parent.document;
            const input = streamlitDoc.querySelector('input[aria-label="qr_value"]');
            if (input) {{
                input.value = decodedText;
                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }}
        }}
        try {{
            let scanner = new Html5QrcodeScanner(
                "{reader_id}",
                {{
                    fps: 10,
                    qrbox: 250,
                    supportedScanTypes: [Html5QrcodeScanType.SCAN_TYPE_CAMERA],
                    videoConstraints: {{ facingMode: "environment" }}
                }}
            );
            scanner.render(onScanSuccess);
        }} catch(e) {{
            console.log("QR scanner init failed:", e);
        }}
    }})();
    </script>
    <!-- nonce:{cycle} -->
    """
    components.html(qr_html, height=400)

def render_gps_capture():
    """Renders the GPS location capture component."""
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
    components.html(gps_html + f"<!-- nonce:{st.session_state['entry_cycle']} -->", height=90)

    gps_value = st.session_state.get("gps_value")
    if gps_value and "," in gps_value:
        latitude, longitude = map(float, gps_value.split(","))
        st.success(f"📍 Location: {latitude}, {longitude}")
    else:
        latitude, longitude = None, None
    return latitude, longitude


# ---------- Main Application Logic ----------
def main():
    render_public_header()

    # Initialize session state defaults
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
    if "username" not in st.session_state:
        st.session_state["username"] = None
    if "role" not in st.session_state:
        st.session_state["role"] = None
    if "must_change_password" not in st.session_state:
        st.session_state["must_change_password"] = 1 # Default to true for new users
    if "entry_cycle" not in st.session_state:
        st.session_state["entry_cycle"] = 0

    # Initialize other form-related session states
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

    if not st.session_state["logged_in"]:
        render_login_form()
    elif st.session_state["must_change_password"] == 1:
        render_change_password_form()
    else:
        render_sidebar_header()
        st.sidebar.write(f"Logged in as: **{st.session_state['username']}** ({st.session_state['role'].capitalize()})")
        if st.sidebar.button("Logout"):
            st.session_state["logged_in"] = False
            st.session_state["username"] = None
            st.session_state["role"] = None
            st.session_state["must_change_password"] = 1
            st.rerun()

        st.title("Inventory Management System")

        master_df = load_master_data()

        if master_df.empty:
            st.warning("Item Master data could not be loaded. Please ensure 'Item_master.xlsx' exists and is accessible.")
            return

        # Item Selection
        st.subheader("🔍 Select Item")
        item_options = master_df.apply(lambda row: f"{row['Item Master ID']} - {row['Item Description']}", axis=1).tolist()
        selected_item_str = st.selectbox("Search and Select Item", options=item_options)

        selected_row = None
        if selected_item_str:
            selected_item_id = selected_item_str.split(" - ")[0]
            selected_row = master_df[master_df["Item Master ID"] == selected_item_id].iloc[0]
            st.write("**Selected Item Details:**")
            st.dataframe(selected_row.to_frame().T, use_container_width=True)

        if selected_row is None:
            st.info("Please select an item to proceed with stock entry.")
            return

        # QR Code and GPS
        st.subheader("Scan QR Code")
        render_qr_scanner()
        st.text_input("QR Code Value", key="qr_value", label_visibility="collapsed")
        qr_code = st.session_state.get("qr_value", "")
        if qr_code:
            st.success(f"QR Code Scanned: {qr_code}")

        latitude, longitude = render_gps_capture()

        # --- STOCK ENTRY FORM ---
        st.subheader("➕ Add New Stock")
        with st.form("stock_entry_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                stock_date = st.date_input("📅 Stock Entry Date", value=date.today(), key="stock_date")
                vendor_name = st.text_input("Vendor Name", key="vendor_name")
                vehicle_number = st.text_input("Vehicle Number", key="vehicle_number")
                thickness = st.number_input("Thickness (mm)", value=None, placeholder="Enter thickness", key="thickness")
                rack = st.number_input("Rack Number", value=None, placeholder="Enter Rack Number", key="rack", format="%d")
                quantity = st.number_input("Enter Quantity", value=0.0, key="quantity")

            with col2:
                invoice_date = st.date_input("📅 Invoice Date", value=date.today(), key="invoice_date")
                make = st.text_input("Make", key="make")
                project_name = st.text_input("Project Name", key="project_name")
                length = st.number_input("Length (Meters)", value=None, placeholder="Enter length", key="length")
                shelf = st.number_input("Shelf Number", value=None, placeholder="Enter Shelf Number", key="shelf", format="%d")
                price = st.number_input("Enter Price per unit", value=0.0, key="price")

            source = st.selectbox("Select Source", ["Spare RM", "Project Inventory", "Off-Cut"], key="source")
            width = st.number_input("Width (Meters)", value=None, placeholder="Enter width", key="width")

            st.markdown("### 📸 Item Snapshot (Optional)")
            snapshot_file = st.camera_input("Take Snapshot", key=f"snapshot_{st.session_state['entry_cycle']}")

            submitted_stock = st.form_submit_button("➕ Add Stock")

            if submitted_stock:
                if quantity <= 0 or price <= 0:
                    st.error("❌ Quantity and Price must be greater than 0")
                else:
                    snapshot_path = None
                    if snapshot_file:
                        safe_name = (
                            qr_code.strip()
                            .replace("/", "_").replace("\\", "_")
                            .replace(" ", "_").replace(":", "_")
                        ) if qr_code else f"photo_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                        snapshot_path = str(IMAGE_DIR / f"{safe_name}.jpg")
                        with open(snapshot_path, "wb") as f:
                            f.write(snapshot_file.getbuffer())

                    stock_data = {
                        "item_master_id": to_native_python_type(selected_row["Item Master ID"]),
                        "item_description": to_native_python_type(selected_row["Item Description"]),
                        "grade_name": to_native_python_type(selected_row["Grade Name"]),
                        "group1_name": to_native_python_type(selected_row["Group1 Name"]),
                        "group2_name": to_native_python_type(selected_row["Group2 Name"]),
                        "section_name": to_native_python_type(selected_row["Section Name"]),
                        "unit_weight": to_native_python_type(selected_row["Unit Wt. (kg/m)"]),
                        "source": to_native_python_type(source),
                        "vendor_name": to_native_python_type(vendor_name),
                        "make": to_native_python_type(make),
                        "vehicle_number": to_native_python_type(vehicle_number),
                        "invoice_date": str(invoice_date) if invoice_date else None,
                        "project_name": to_native_python_type(project_name),
                        "thickness": to_native_python_type(thickness),
                        "length": to_native_python_type(length),
                        "width": to_native_python_type(width),
                        "qr_code": to_native_python_type(qr_code),
                        "snapshot": snapshot_path,
                        "latitude": to_native_python_type(latitude),
                        "longitude": to_native_python_type(longitude),
                        "rack": to_native_python_type(rack),
                        "shelf": to_native_python_type(shelf),
                        "quantity": to_native_python_type(quantity),
                        "price": to_native_python_type(price),
                        "stock_date": str(stock_date) if stock_date else None,
                        "added_by": st.session_state.get("username", "Unknown")
                    }

                    try:
                        append_stock(stock_data)
                        st.success("✅ Stock entry successful!")
                        reset_stock_entry_form_state()
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Failed to add stock: {e}")
                        if DEBUG_MODE:
                            import traceback
                            st.error(traceback.format_exc())

        # ---------- Current Stock Display and Deletion ----------
        st.subheader("📊 Current Stock")
        stock_df = load_stock_data()

        if not stock_df.empty:
            st.dataframe(stock_df, use_container_width=True)

            # Single Row Delete
            st.subheader("🗑 Delete Single Stock Entry")
            # Ensure 'id' column exists and is numeric before converting to int
            if 'id' in stock_df.columns and pd.api.types.is_numeric_dtype(stock_df['id']):
                row_to_delete_id = st.selectbox("Select ID to Delete", stock_df["id"].astype(int).tolist())
            else:
                row_to_delete_id = None
                st.info("No deletable stock entries found or 'id' column is missing/invalid.")

            if st.button("Delete Selected Entry") and row_to_delete_id is not None:
                delete_stock_row(
                    row_to_delete_id,
                    st.session_state.get("username"),
                    st.session_state.get("role")
                )
                st.success("✅ Entry deleted successfully")
                st.rerun()

            # Bulk Delete (ADMIN ONLY)
            if st.session_state.get("role") == "admin":
                st.markdown("### 🚨 Bulk Delete (Admin Only)")
                if not stock_df.empty and 'id' in stock_df.columns:
                    min_id = int(stock_df["id"].min())
                    max_id = int(stock_df["id"].max())

                    c1, c2 = st.columns(2)
                    with c1:
                        start_id = st.number_input("From ID", min_value=min_id, max_value=max_id, value=min_id)
                    with c2:
                        end_id = st.number_input("To ID", min_value=min_id, max_value=max_id, value=max_id)

                    if st.button("Delete Range"):
                        if start_id > end_id:
                            st.error("Start ID cannot be greater than End ID")
                        else:
                            delete_stock_range(start_id, end_id)
                            st.success(f"✅ Deleted records from ID {start_id} to {end_id}")
                            st.rerun()
                else:
                    st.info("No stock entries available for bulk deletion.")
        else:
            st.info("No stock entries available.")


if __name__ == "__main__":
    main()
