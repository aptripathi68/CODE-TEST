#THE BELOW CODE SUCCESSFUL CAPTURES INVENTORY INPUT, GPS LOCATION, QR CODE, SNAPSHOT 





import streamlit as st
import pandas as pd
import csv
import os
import sqlite3
import hashlib

# ---------- Simple Authentication ----------

def check_login(username, password):
    users = {
        "admin": hashlib.sha256("admin123".encode()).hexdigest(),
        "arun": hashlib.sha256("inventory".encode()).hexdigest()
    }

    if username in users:
        return users[username] == hashlib.sha256(password.encode()).hexdigest()
    return False



# File paths
STOCK_FILE = DB_FILE = "inventory.db"
MASTER_FILE = "Item_master.xlsx"

# ---------- Helper Functions ----------

def initialize_database():
    """Create inventory table if it doesn't exist."""
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
        stock_date TEXT
    )
""")

    conn.commit()
    conn.close()

def append_stock(selected_row, source, vendor_name, make,
                 vehicle_number, invoice_date, project_name,
                 thickness, length, width,
                 qr_code, snapshot_path,
                 latitude, longitude,
                 rack, shelf,
                 quantity, price, stock_date):
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
    stock_date
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    selected_row["Item Master ID"],
    selected_row["Item Description"],
    selected_row["Grade Name"],
    selected_row["Group1 Name"],
    selected_row["Group2 Name"],
    selected_row["Section Name"],
    selected_row["Unit Wt. (kg/m)"],
    source,
    vendor_name,
    make,
    vehicle_number,
    str(invoice_date),
    project_name,
    thickness,
    length,
    width,
    qr_code,
    snapshot_path,
    latitude,
    longitude,
    rack,
    shelf,
    quantity,
    price,
    str(stock_date)
))

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


def delete_stock_row(row_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM inventory WHERE id = ?", (row_id,))
    conn.commit()
    conn.close()

# Database initialization
initialize_database()

# ---------- Streamlit Interface ----------

# ---------- Login System ----------

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 Login Required")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if check_login(username, password):
            st.session_state.logged_in = True
            st.success("Login Successful!")
            st.rerun()
        else:
            st.error("Invalid Username or Password")

    st.stop()


st.title("📦 Stock Entry System")

# Initialize stock file
initialize_database()

# Load master data
master_df = load_master_data()

# ---------- 1️⃣ Select Category ----------
categories = sorted(master_df["Group2 Name"].dropna().unique())
selected_category = st.selectbox("Select Category", categories)

filtered_category = master_df[
    master_df["Group2 Name"] == selected_category
]

# ---------- 2️⃣ Select Grade ----------
grades = sorted(filtered_category["Grade Name"].dropna().unique())
selected_grade = st.selectbox("Select Grade", grades)

filtered_grade = filtered_category[
    filtered_category["Grade Name"] == selected_grade
]

# ---------- 3️⃣ Select Item ----------
selected_item_index = st.selectbox(
    "Select Item",
    filtered_grade.index,
    format_func=lambda x: filtered_grade.loc[x, "Item Description"]
)

selected_row = filtered_grade.loc[selected_item_index]

# ---------- Dimension Fields ----------
thickness = st.number_input("Thickness", value=None, placeholder="Enter thickness")
length = st.number_input("Length (Meters)", value=None, placeholder="Enter length")
width = st.number_input("Width (Meters)", value=None, placeholder="Enter width")


# ---------- PROFESSIONAL QR SCANNER ----------
import streamlit.components.v1 as components

st.markdown("### 📷 Scan QR Code")

# Hidden field to store scanned value
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
        videoConstraints: {
            facingMode: { exact: "environment" }
        }
    }
);

html5QrcodeScanner.render(onScanSuccess);
</script>
"""

components.html(qr_html, height=400)

qr_code = st.session_state.get("qr_value")
    

# ---------- GPS Location ----------

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
        {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 0
        }
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
    
# ---------- Rack & Shelf ----------
rack = st.number_input("Rack Number", min_value=0, step=1)
shelf = st.number_input("Shelf Number", min_value=0, step=1)

# Display item details
st.write("**Item Details:**")
st.write({
    "Item Master ID": selected_row["Item Master ID"],
    "Description": selected_row["Item Description"],
    "Grade": selected_row["Grade Name"],
    "Unit Weight (kg/m)": selected_row["Unit Wt. (kg/m)"]
})

from datetime import date

# Date Input
stock_date = st.date_input(
    "📅 Select Stock Entry Date",
    value=date.today()
)

# Source, Quantity & Price input
from datetime import date

vendor_name = st.text_input("Vendor Name")
make = st.text_input("Make")
vehicle_number = st.text_input("Vehicle Number")

invoice_date = st.date_input(
    "📅 Select Invoice Date",
    value=date.today()
)

project_name = st.text_input("Project Name")

source_options = ["Spare RM", "Project Inventory", "Off-Cut"]

source = st.selectbox(
    "Select Source",
    source_options
)
quantity = st.number_input("Enter Quantity", value=None, placeholder="Enter quantity")
price = st.number_input("Enter Price per unit", value=None, placeholder="Enter price")
st.markdown("### 📸 Item Snapshot (Optional)")
snapshot = st.camera_input("Take Snapshot")

# Add stock button
import os

if st.button("➕ Add Stock"):

    # Validate
    if quantity is None or price is None or quantity <= 0 or price <= 0:
        st.error("❌ Quantity and Price must be greater than 0")

    else:

        snapshot_path = None

        # Create images folder if not exists
        if not os.path.exists("images"):
            os.makedirs("images")

        # Save snapshot only if taken
        if snapshot is not None:

            from datetime import datetime

            qr_value = st.session_state.get("qr_value")

            if qr_value and isinstance(qr_value, str):

                safe_qr = (
                    qr_value.strip()
                    .replace("/", "_")
                    .replace("\\", "_")
                    .replace(" ", "_")
                    .replace(":", "_")
                )

                snapshot_path = f"images/{safe_qr}.jpg"

            else:
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                snapshot_path = f"images/photo_{timestamp}.jpg"

            with open(snapshot_path, "wb") as f:
                f.write(snapshot.getbuffer())

        # Insert into database (ALWAYS inside button block)
        append_stock(
            selected_row,
            source,
            vendor_name,
            make,
            vehicle_number,
            invoice_date,
            project_name,
            thickness,
            length,
            width,
            qr_code if qr_code else None,
            snapshot_path,
            latitude,
            longitude,
            rack,
            shelf,
            quantity,
            price,
            stock_date
        )

        st.success("✅ Stock entry successful!")

        # Reset QR & GPS to prevent repeat
        st.session_state.pop("qr_value", None)
        st.session_state.pop("gps_value", None)

        st.rerun()

# Display current stock
st.subheader("📊 Current Stock")
stock_df = load_stock_data()

if not stock_df.empty:

    # Hide internal column
    display_df = stock_df.drop(columns=["item_master_id"], errors="ignore")

    # Make display index start from 1
    display_df.index = range(1, len(display_df) + 1)

    st.dataframe(display_df)

    # ---------- Export to Excel ----------
    import io
    buffer = io.BytesIO()
    display_df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)

    st.download_button(
        label="📥 Download Stock as Excel",
        data=buffer,
        file_name="Current_Stock.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # ---------- Delete Section ----------
    st.markdown("### 🗑 Delete Stock Entry")

    row_to_delete = st.selectbox(
        "Select ID to Delete",
        stock_df["id"]
    )

    if st.button("Delete Selected Entry"):
        delete_stock_row(row_to_delete)
        st.success("✅ Stock entry deleted successfully!")
        st.rerun()

else:
    st.info("No stock entries available.")

st.markdown("### 🗑 Bulk Delete (By ID Range)")

if not stock_df.empty:

    min_id = int(stock_df["id"].min())
    max_id = int(stock_df["id"].max())

    col1, col2 = st.columns(2)

    with col1:
        start_id = st.number_input(
            "From ID",
            min_value=min_id,
            max_value=max_id,
            step=1
        )

    with col2:
        end_id = st.number_input(
            "To ID",
            min_value=min_id,
            max_value=max_id,
            step=1
        )

    if st.button("Delete Range"):

        if start_id > end_id:
            st.error("Start ID cannot be greater than End ID")
        else:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM inventory WHERE id BETWEEN ? AND ?",
                (start_id, end_id)
            )
            conn.commit()
            conn.close()

            st.success(f"Deleted records from ID {start_id} to {end_id}")
            st.rerun()

else:
    st.info("No records available for deletion.")
