import streamlit as st
import pandas as pd
import csv
import os
import sqlite3
import hashlib
import json

# ---------- USER MANAGEMENT SYSTEM ----------

USERS_FILE = "users.json"

def load_users():
    if not os.path.exists(USERS_FILE):
        default_users = {
            "admin": {
                "password": hashlib.sha256("admin123".encode()).hexdigest(),
                "role": "admin"
            }
        }
        with open(USERS_FILE, "w") as f:
            json.dump(default_users, f)
        return default_users

    with open(USERS_FILE, "r") as f:
        return json.load(f)


def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)


def verify_login(username, password):
    users = load_users()
    if username in users:
        hashed = hashlib.sha256(password.encode()).hexdigest()
        if hashed == users[username]["password"]:
            return users[username]["role"]
    return None

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
    st.session_state.username = None
    st.session_state.role = None

if not st.session_state.logged_in:

    st.title("🔐 Login Required")

    username = st.text_input("Username", key="login_user")
    password = st.text_input("Password", type="password", key="login_pass")

    if st.button("Login", key="login_btn"):
        role = verify_login(username, password)

        if role:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.role = role
            st.success("Login Successful!")
            st.experimental_rerun()
        else:
            st.error("Invalid Username or Password")

    st.stop()

# ---------- AFTER LOGIN ----------
st.sidebar.success(f"Logged in as: {st.session_state.username} ({st.session_state.role})")

if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.role = None
    st.experimental_rerun()


# ---------- ADMIN PANEL ----------
if st.session_state.role == "admin":

    st.sidebar.markdown("### 🛠 Admin Panel")

    if st.sidebar.button("Create New User"):

        st.subheader("👤 Create New User")

        new_username = st.text_input("New Username", key="new_user")
        default_password = st.text_input("Default Password", value="user123", key="new_pass")
        new_role = st.selectbox("Role", ["user"], key="new_role")

        if st.button("Create User", key="create_user_btn"):

            users = load_users()

            if new_username in users:
                st.error("User already exists!")
            elif new_username.strip() == "":
                st.error("Username cannot be empty!")
            else:
                users[new_username] = {
                    "password": hashlib.sha256(default_password.encode()).hexdigest(),
                    "role": new_role
                }
                save_users(users)
                st.success(f"User '{new_username}' created successfully!")
                

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
thickness = st.number_input("thickness", min_value=0.0, step=0.01)
length = st.number_input("length (Meters)", min_value=0.0, step=0.01)
width = st.number_input("width (Meters)", min_value=0.0, step=0.01)

# ---------- QR Scan from Camera ----------
from pyzbar.pyzbar import decode
from PIL import Image

qr_code = None
snapshot = st.camera_input("📸 Scan QR Code")

if snapshot is not None:
    image = Image.open(snapshot)
    decoded_objects = decode(image)

    if decoded_objects:
        qr_code = decoded_objects[0].data.decode("utf-8")
        st.success(f"QR Code Detected: {qr_code}")
    else:
        st.warning("No QR code detected.")

# ---------- Auto GPS Location ----------
from streamlit_geolocation import streamlit_geolocation

location = streamlit_geolocation()

if location:
    latitude = location["latitude"]
    longitude = location["longitude"]
    st.write("📍 Latitude:", latitude)
    st.write("📍 Longitude:", longitude)
else:
    latitude = None
    longitude = None

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
quantity = st.number_input("Enter Quantity", min_value=0.0, step=0.01)
price = st.number_input("Enter Price per unit", min_value=0.0, step=0.01)

# Add stock button
import os

if st.button("➕ Add Stock"):

    if quantity <= 0 or price <= 0:
        st.error("❌ Quantity and Price must be greater than 0")
    else:

        snapshot_path = None

        # Create images folder if not exists
        if not os.path.exists("images"):
            os.makedirs("images")

        # Save snapshot only if taken
        if snapshot is not None:
            if qr_code:
                safe_qr = qr_code.replace("/", "_").replace(" ", "_")
                snapshot_path = f"images/{safe_qr}.jpg"
            else:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                snapshot_path = f"images/photo_{timestamp}.jpg"

            with open(snapshot_path, "wb") as f:
                f.write(snapshot.getbuffer())

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
