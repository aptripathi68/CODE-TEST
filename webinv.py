"""
Kalpadeep Industries - Inventory Management System
A comprehensive inventory tracking system with QR scanning, GPS, and multi-user support
"""

import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import base64
import os
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
from contextlib import contextmanager
import logging
import streamlit.components.v1 as components
import numpy as np

# ---------- Page Configuration ----------
st.set_page_config(
    page_title="Kalpadeep IMS",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- Configuration Class ----------
class Config:
    """Application configuration settings"""
    
    # Paths
    BASE_DIR = Path(__file__).resolve().parent
    DB_FILE = str(BASE_DIR / "inventory.db")
    MASTER_FILE = str(BASE_DIR / "Item_master.xlsx")
    IMAGE_DIR = BASE_DIR / "images"
    LOGO_PATH = BASE_DIR / "Kalpadeep Logo.jpg"
    
    # Authentication
    DEFAULT_PASSWORD = "123456"
    ADMIN_PASSWORD = "admin123"
    
    # Application settings
    DEBUG_MODE = False
    QR_BOX_SIZE = 250
    GPS_TIMEOUT = 10000
    GPS_MAX_AGE = 0
    
    # Database Queries
    CREATE_USERS_TABLE = """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT,
            must_change_password INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    
    CREATE_INVENTORY_TABLE = """
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
            added_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    
    INSERT_INVENTORY = """
        INSERT INTO inventory (
            item_master_id, item_description, grade_name, group1_name,
            group2_name, section_name, unit_weight, source, vendor_name,
            make, vehicle_number, invoice_date, project_name, thickness,
            length, width, qr_code, snapshot, latitude, longitude,
            rack, shelf, quantity, price, stock_date, added_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    SELECT_USER = "SELECT role, must_change_password FROM users WHERE username = ? AND password = ?"
    SELECT_ALL_USERS = "SELECT id, username, role FROM users ORDER BY id"
    UPDATE_USER_PASSWORD = "UPDATE users SET password = ?, must_change_password = ? WHERE username = ?"
    DELETE_USER = "DELETE FROM users WHERE username = ?"
    INSERT_USER = "INSERT INTO users (username, password, role, must_change_password) VALUES (?, ?, ?, ?)"

# ---------- Logging Configuration ----------
logging.basicConfig(
    level=logging.DEBUG if Config.DEBUG_MODE else logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ---------- Database Utilities ----------
class DatabaseManager:
    """Centralized database operations with context management"""
    
    @staticmethod
    @contextmanager
    def get_connection():
        """Context manager for database connections"""
        conn = sqlite3.connect(Config.DB_FILE)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    @staticmethod
    def initialize():
        """Initialize all database tables"""
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(Config.CREATE_USERS_TABLE)
            cursor.execute(Config.CREATE_INVENTORY_TABLE)
            DatabaseManager._create_default_admin(cursor)
    
    @staticmethod
    def _create_default_admin(cursor):
        """Create default admin user if not exists"""
        admin_password = hashlib.sha256(Config.ADMIN_PASSWORD.encode()).hexdigest()
        cursor.execute("SELECT * FROM users WHERE username = ?", ("admin",))
        if not cursor.fetchone():
            cursor.execute(
                Config.INSERT_USER,
                ("admin", admin_password, "admin", 0)
            )
    
    @staticmethod
    def execute_query(query: str, params: tuple = ()) -> Optional[List[sqlite3.Row]]:
        """Execute a query and return results"""
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            if query.strip().upper().startswith('SELECT'):
                return cursor.fetchall()
            return None
    
    @staticmethod
    def execute_insert(query: str, params: tuple) -> int:
        """Execute an insert and return last row id"""
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.lastrowid

# Initialize database
DatabaseManager.initialize()

# ---------- Data Processing Utilities ----------
class DataProcessor:
    """Handle data cleaning and conversion"""
    
    @staticmethod
    def clean_value(val):
        """Clean pandas NA values"""
        return None if pd.isna(val) else val
    
    @staticmethod
    def to_native(val):
        """Convert numpy types to Python native types"""
        if isinstance(val, (np.integer, np.int64)):
            return int(val)
        if isinstance(val, (np.floating, np.float64)):
            return float(val)
        return val
    
    @staticmethod
    def safe_filename(text: str) -> str:
        """Convert text to safe filename"""
        if not text:
            return "photo"
        return "".join(c for c in text if c.isalnum() or c in ('-', '_')).strip() or "photo"

# ---------- Authentication Manager ----------
class AuthManager:
    """Handle user authentication and management"""
    
    @staticmethod
    def check_login(username: str, password: str) -> Dict[str, Any]:
        """Authenticate user credentials"""
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        result = DatabaseManager.execute_query(
            Config.SELECT_USER,
            (username, hashed_password)
        )
        
        if result:
            return {
                "success": True,
                "role": result[0][0],
                "must_change_password": result[0][1]
            }
        return {"success": False}
    
    @staticmethod
    def create_user(username: str, role: str = "user") -> Tuple[bool, str]:
        """Create a new user"""
        if not username or not username.strip():
            return False, "Username cannot be empty"
        
        try:
            default_password = hashlib.sha256(Config.DEFAULT_PASSWORD.encode()).hexdigest()
            DatabaseManager.execute_insert(
                Config.INSERT_USER,
                (username.strip(), default_password, role, 1)
            )
            return True, f"User created successfully. Default password: {Config.DEFAULT_PASSWORD}"
        except sqlite3.IntegrityError:
            return False, "Username already exists"
    
    @staticmethod
    def update_password(username: str, new_password: str, force_change: int = 0) -> bool:
        """Update user password"""
        if len(new_password) < 6:
            return False
        hashed = hashlib.sha256(new_password.encode()).hexdigest()
        DatabaseManager.execute_query(
            Config.UPDATE_USER_PASSWORD,
            (hashed, force_change, username)
        )
        return True
    
    @staticmethod
    def delete_user(username: str, current_user: str) -> Tuple[bool, str]:
        """Delete a user"""
        if username == "admin":
            return False, "Admin account cannot be deleted"
        if username == current_user:
            return False, "You cannot delete yourself"
        
        DatabaseManager.execute_query(Config.DELETE_USER, (username,))
        return True, "User deleted successfully"
    
    @staticmethod
    def get_all_users() -> pd.DataFrame:
        """Get all users as DataFrame"""
        result = DatabaseManager.execute_query(Config.SELECT_ALL_USERS)
        if not result:
            return pd.DataFrame()
        return pd.DataFrame([dict(row) for row in result])

# ---------- Inventory Manager ----------
class InventoryManager:
    """Handle inventory operations"""
    
    @staticmethod
    def load_master_data() -> pd.DataFrame:
        """Load item master data from Excel"""
        try:
            df = pd.read_excel(Config.MASTER_FILE)
            df.columns = df.columns.str.strip()
            return df
        except Exception as e:
            logger.error(f"Failed to load master data: {e}")
            st.error(f"Error loading master data: {e}")
            return pd.DataFrame()
    
    @staticmethod
    def load_stock_data() -> pd.DataFrame:
        """Load current stock data"""
        with DatabaseManager.get_connection() as conn:
            df = pd.read_sql_query("SELECT * FROM inventory ORDER BY id DESC", conn)
        
        if not df.empty and 'quantity' in df.columns and 'price' in df.columns:
            df["total_value"] = df["quantity"] * df["price"]
        return df
    
    @staticmethod
    def add_stock_entry(data: Dict[str, Any]) -> bool:
        """Add new stock entry"""
        try:
            # Prepare values
            values = tuple(
                DataProcessor.to_native(data.get(field)) 
                for field in [
                    'item_master_id', 'item_description', 'grade_name', 'group1_name',
                    'group2_name', 'section_name', 'unit_weight', 'source', 'vendor_name',
                    'make', 'vehicle_number', 'invoice_date', 'project_name', 'thickness',
                    'length', 'width', 'qr_code', 'snapshot_path', 'latitude', 'longitude',
                    'rack', 'shelf', 'quantity', 'price', 'stock_date', 'added_by'
                ]
            )
            
            DatabaseManager.execute_insert(Config.INSERT_INVENTORY, values)
            logger.info(f"Stock entry added by {data.get('added_by')}")
            return True
        except Exception as e:
            logger.error(f"Failed to add stock: {e}")
            return False
    
    @staticmethod
    def delete_stock_entry(row_id: int, username: str, role: str) -> bool:
        """Delete single stock entry"""
        if role == 'admin':
            query = "DELETE FROM inventory WHERE id = ?"
        else:
            query = "DELETE FROM inventory WHERE id = ? AND added_by = ?"
            params = (row_id, username)
        
        DatabaseManager.execute_query(query, params if role != 'admin' else (row_id,))
        return True
    
    @staticmethod
    def bulk_delete(start_id: int, end_id: int) -> int:
        """Bulk delete stock entries (admin only)"""
        DatabaseManager.execute_query(
            "DELETE FROM inventory WHERE id BETWEEN ? AND ?",
            (start_id, end_id)
        )
        return end_id - start_id + 1
    
    @staticmethod
    def save_snapshot(image_data, qr_code: str) -> Optional[str]:
        """Save snapshot image to disk"""
        if not image_data:
            return None
        
        Config.IMAGE_DIR.mkdir(exist_ok=True)
        
        filename = f"{DataProcessor.safe_filename(qr_code)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        filepath = Config.IMAGE_DIR / filename
        
        with open(filepath, "wb") as f:
            f.write(image_data.getbuffer())
        
        return str(filepath)

# ---------- UI Components ----------
class UIComponents:
    """Reusable UI components"""
    
    @staticmethod
    def render_header():
        """Render company header"""
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            if Config.LOGO_PATH.exists():
                st.image(str(Config.LOGO_PATH), width=200)
            
            st.markdown(
                """
                <div style='text-align:left; font-size:22px; font-weight:700; margin-top:4px;'>
                    KALPADEEP INDUSTRIES PVT LTD
                </div>
                <div style='text-align:left; color:#B87333; font-size:18px; font-weight:500; 
                           letter-spacing:1px; margin-top:4px;'>
                    Inventory Management System
                </div>
                """,
                unsafe_allow_html=True
            )
        st.divider()
    
    @staticmethod
    def render_sidebar_header():
        """Render sidebar header"""
        if Config.LOGO_PATH.exists():
            st.sidebar.image(str(Config.LOGO_PATH), use_container_width=True)
        st.sidebar.markdown("**KALPADEEP INDUSTRIES PVT LTD**")
        st.sidebar.caption("Inventory Management System")
        st.sidebar.markdown("---")
    
    @staticmethod
    def render_logout_button():
        """Render logout button"""
        col1, col2 = st.columns([6, 1])
        with col2:
            if st.button("🚪 Logout", use_container_width=True):
                st.session_state.clear()
                st.rerun()
    
    @staticmethod
    def render_qr_scanner(cycle: int):
        """Render QR code scanner"""
        st.markdown("### 📷 Scan QR Code")
        
        st.text_input("qr_value", key="qr_value", label_visibility="collapsed")
        
        qr_html = f"""
        <script src="https://unpkg.com/html5-qrcode"></script>
        <div id="reader_{cycle}" style="width:300px;"></div>
        <script>
        (function() {{
            const el = document.getElementById("reader_{cycle}");
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
                    "reader_{cycle}",
                    {{
                        fps: 10,
                        qrbox: {Config.QR_BOX_SIZE},
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
    
    @staticmethod
    def render_gps_locator():
        """Render GPS location component"""
        st.markdown("### 📍 Auto GPS Location")
        st.text_input("gps_value", key="gps_value", label_visibility="collapsed")
        
        gps_html = f"""
        <script>
        function getLocation() {{
            if (!navigator.geolocation) {{
                alert("Geolocation is not supported by this browser.");
                return;
            }}
            navigator.geolocation.getCurrentPosition(
                function(position) {{
                    const lat = position.coords.latitude;
                    const lon = position.coords.longitude;
                    const loc = lat + "," + lon;
                    
                    const streamlitDoc = window.parent.document;
                    const input = streamlitDoc.querySelector('input[aria-label="gps_value"]');
                    
                    if (input){{
                        input.value = loc;
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }}
                    alert("Location Captured Successfully");
                }},
                function(error) {{
                    alert("Error capturing location: " + error.message);
                }},
                {{ enableHighAccuracy: true, timeout: {Config.GPS_TIMEOUT}, maximumAge: {Config.GPS_MAX_AGE} }}
            );
        }}
        </script>
        
        <button onclick="getLocation()" style="
        padding:10px 14px;
        background-color:#007BFF;
        color:white;
        border:none;
        border-radius:6px;
        font-size:16px;
        cursor:pointer;">
        📍 Capture GPS Location
        </button>
        """
        components.html(gps_html, height=90)

# ---------- Admin Panel ----------
class AdminPanel:
    """Admin panel UI and functionality"""
    
    @staticmethod
    def render():
        """Render admin panel"""
        st.sidebar.markdown("### 👨‍💼 Admin Panel")
        
        # User creation
        with st.sidebar.form("create_user_form", clear_on_submit=True):
            new_user = st.text_input("New Username")
            if st.form_submit_button("Create User", use_container_width=True):
                success, message = AuthManager.create_user(new_user)
                if success:
                    st.sidebar.success(message)
                    st.rerun()
                else:
                    st.sidebar.error(message)
        
        st.sidebar.markdown("---")
        
        # User management
        st.subheader("👤 User Management")
        user_df = AuthManager.get_all_users()
        
        if user_df.empty:
            st.info("No users found.")
        else:
            st.dataframe(user_df, use_container_width=True)
            
            selected_user = st.selectbox(
                "Select User",
                user_df["username"].tolist(),
                key="admin_selected_user"
            )
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🔑 Reset Password", key="reset_pwd", use_container_width=True):
                    AuthManager.update_password(selected_user, Config.DEFAULT_PASSWORD, 1)
                    st.success(f"Password reset to {Config.DEFAULT_PASSWORD}")
                    st.rerun()
            
            with col2:
                if st.button("❌ Delete User", key="delete_user", use_container_width=True):
                    success, message = AuthManager.delete_user(
                        selected_user, 
                        st.session_state.get("username")
                    )
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

# ---------- Stock Entry Form ----------
class StockEntryForm:
    """Stock entry form handling"""
    
    def __init__(self, master_df: pd.DataFrame):
        self.master_df = master_df
        self.selected_row = None
    
    def render(self) -> Optional[Dict[str, Any]]:
        """Render the stock entry form"""
        # Category selection
        categories = sorted(self.master_df["Group2 Name"].dropna().unique())
        selected_category = st.selectbox("Select Category", categories)
        
        filtered_category = self.master_df[self.master_df["Group2 Name"] == selected_category]
        
        # Grade selection
        grades = sorted(filtered_category["Grade Name"].dropna().unique())
        selected_grade = st.selectbox("Select Grade", grades)
        
        filtered_grade = filtered_category[filtered_category["Grade Name"] == selected_grade]
        
        # Item selection
        selected_item_index = st.selectbox(
            "Select Item",
            filtered_grade.index,
            format_func=lambda x: filtered_grade.loc[x, "Item Description"]
        )
        
        self.selected_row = filtered_grade.loc[selected_item_index]
        
        # Display item details
        st.write("**Item Details:**")
        st.json({
            "Item Master ID": str(self.selected_row["Item Master ID"]),
            "Description": self.selected_row["Item Description"],
            "Grade": self.selected_row["Grade Name"],
            "Unit Weight (kg/m)": float(self.selected_row["Unit Wt. (kg/m)"])
        })
        
        # QR Scanner
        UIComponents.render_qr_scanner(st.session_state["entry_cycle"])
        
        # GPS
        UIComponents.render_gps_locator()
        
        # Parse GPS
        gps_value = st.session_state.get("gps_value")
        if gps_value and "," in gps_value:
            lat, lon = map(float, gps_value.split(","))
            st.success(f"📍 Location: {lat}, {lon}")
        else:
            lat, lon = None, None
        
        # Stock entry form
        with st.form("stock_entry_form", clear_on_submit=True):
            # Date inputs
            col1, col2 = st.columns(2)
            with col1:
                stock_date = st.date_input("📅 Stock Entry Date", value=date.today())
            with col2:
                invoice_date = st.date_input("📅 Invoice Date", value=date.today())
            
            # Text inputs
            col1, col2 = st.columns(2)
            with col1:
                vendor_name = st.text_input("Vendor Name")
                make = st.text_input("Make")
                rack = st.number_input("Rack Number", value=None, placeholder="Enter Rack")
            with col2:
                vehicle_number = st.text_input("Vehicle Number")
                project_name = st.text_input("Project Name")
                shelf = st.number_input("Shelf Number", value=None, placeholder="Enter Shelf")
            
            # Source selection
            source = st.selectbox("Select Source", ["Spare RM", "Project Inventory", "Off-Cut"])
            
            # Dimensions
            col1, col2, col3 = st.columns(3)
            with col1:
                thickness = st.number_input("Thickness (mm)", value=None, placeholder="Thickness")
            with col2:
                length = st.number_input("Length (Meters)", value=None, placeholder="Length")
            with col3:
                width = st.number_input("Width (Meters)", value=None, placeholder="Width")
            
            # Quantity and Price
            col1, col2 = st.columns(2)
            with col1:
                quantity = st.number_input("Quantity", min_value=0.0, value=0.0, step=0.1)
            with col2:
                price = st.number_input("Price per unit", min_value=0.0, value=0.0, step=0.01)
            
            # Snapshot
            st.markdown("### 📸 Item Snapshot (Optional)")
            snapshot = st.camera_input(
                "Take Snapshot", 
                key=f"snapshot_{st.session_state['entry_cycle']}"
            )
            
            submitted = st.form_submit_button("➕ Add Stock", type="primary", use_container_width=True)
            
            if submitted:
                return {
                    'selected_row': self.selected_row,
                    'source': source,
                    'vendor_name': vendor_name,
                    'make': make,
                    'vehicle_number': vehicle_number,
                    'invoice_date': invoice_date,
                    'project_name': project_name,
                    'thickness': thickness,
                    'length': length,
                    'width': width,
                    'qr_code': st.session_state.get("qr_value", ""),
                    'snapshot': snapshot,
                    'latitude': lat,
                    'longitude': lon,
                    'rack': rack,
                    'shelf': shelf,
                    'quantity': quantity,
                    'price': price,
                    'stock_date': stock_date
                }
        
        return None

# ---------- Stock Display ----------
class StockDisplay:
    """Stock display and management"""
    
    @staticmethod
    def render():
        """Render stock display"""
        st.subheader("📊 Current Stock")
        stock_df = InventoryManager.load_stock_data()
        
        if stock_df.empty:
            st.info("No stock entries available.")
            return
        
        # Display stock
        st.dataframe(stock_df, use_container_width=True)
        
        # Single delete
        st.subheader("🗑 Delete Single Stock Entry")
        row_to_delete = st.selectbox("Select ID to Delete", stock_df["id"].tolist())
        
        if st.button("Delete Selected Entry", use_container_width=True):
            InventoryManager.delete_stock_entry(
                row_to_delete,
                st.session_state.get("username"),
                st.session_state.get("role")
            )
            st.success("✅ Entry deleted successfully")
            st.rerun()
        
        # Bulk delete for admin
        if st.session_state.get("role") == "admin":
            st.markdown("### 🚨 Bulk Delete (Admin Only)")
            
            min_id = int(stock_df["id"].min())
            max_id = int(stock_df["id"].max())
            
            col1, col2 = st.columns(2)
            with col1:
                start_id = st.number_input("From ID", min_value=min_id, max_value=max_id, value=min_id)
            with col2:
                end_id = st.number_input("To ID", min_value=min_id, max_value=max_id, value=max_id)
            
            if st.button("Delete Range", use_container_width=True):
                if start_id > end_id:
                    st.error("Start ID cannot be greater than End ID")
                else:
                    deleted = InventoryManager.bulk_delete(start_id, end_id)
                    st.success(f"✅ Deleted {deleted} records")
                    st.rerun()

# ---------- Session State Manager ----------
class SessionManager:
    """Manage session state"""
    
    @staticmethod
    def initialize():
        """Initialize session state with defaults"""
        defaults = {
            "logged_in": False,
            "stock_added": False,
            "qr_value": "",
            "gps_value": "",
            "entry_cycle": 0,
            "reset_qr_gps": False
        }
        
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value

# ---------- Main Application ----------
class InventoryApp:
    """Main application class"""
    
    def __init__(self):
        SessionManager.initialize()
    
    def run(self):
        """Main application entry point"""
        # Always show header
        UIComponents.render_header()
        
        # Authentication
        if not st.session_state["logged_in"]:
            self._handle_login()
            return
        
        # Password change
        if st.session_state.get("must_change_password") == 1:
            self._handle_password_change()
            return
        
        # Main application
        UIComponents.render_sidebar_header()
        UIComponents.render_logout_button()
        
        # Admin panel
        if st.session_state.get("role") == "admin":
            AdminPanel.render()
        
        # Load master data
        master_df = InventoryManager.load_master_data()
        if master_df.empty:
            st.error("Failed to load master data. Please check the file.")
            return
        
        # Reset QR/GPS if requested
        if st.session_state["reset_qr_gps"]:
            st.session_state["qr_value"] = ""
            st.session_state["gps_value"] = ""
            st.session_state["reset_qr_gps"] = False
        
        # Stock entry form
        form = StockEntryForm(master_df)
        form_data = form.render()
        
        # Handle form submission
        if form_data:
            self._handle_stock_submission(form_data)
        
        # Display current stock
        StockDisplay.render()
    
    def _handle_login(self):
        """Handle login process"""
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.button("Login", use_container_width=True):
            result = AuthManager.check_login(username, password)
            if result["success"]:
                st.session_state.update({
                    "logged_in": True,
                    "username": username,
                    "role": result["role"],
                    "must_change_password": result["must_change_password"]
                })
                st.rerun()
            else:
                st.error("Invalid Username or Password")
    
    def _handle_password_change(self):
        """Handle password change process"""
        st.title("🔑 Change Default Password")
        
        new_password = st.text_input("New Password", type="password")
        
        if st.button("Update Password", use_container_width=True):
            if len(new_password) < 6:
                st.error("Password must be at least 6 characters long")
            elif AuthManager.update_password(st.session_state["username"], new_password, 0):
                st.session_state["must_change_password"] = 0
                st.success("Password updated successfully!")
                st.rerun()
    
    def _handle_stock_submission(self, form_data: Dict[str, Any]):
        """Handle stock form submission"""
        # Validate
        if form_data['quantity'] <= 0 or form_data['price'] <= 0:
            st.error("❌ Quantity and Price must be greater than 0")
            return
        
        # Clean selected row
        row = form_data.pop('selected_row')
        for col in ["Item Master ID", "Item Description", "Grade Name",
                    "Group1 Name", "Group2 Name", "Section Name", "Unit Wt. (kg/m)"]:
            row[col] = DataProcessor.clean_value(row[col])
        
        # Save snapshot
        snapshot_path = InventoryManager.save_snapshot(
            form_data.pop('snapshot'),
            form_data['qr_code']
        )
        
        # Prepare stock data
        stock_data = {
            'item_master_id': row["Item Master ID"],
            'item_description': row["Item Description"],
            'grade_name': row["Grade Name"],
            'group1_name': row["Group1 Name"],
            'group2_name': row["Group2 Name"],
            'section_name': row["Section Name"],
            'unit_weight': row["Unit Wt. (kg/m)"],
            'snapshot_path': snapshot_path,
            'added_by': st.session_state.get("username"),
            **form_data
        }
        
        # Add stock
        if InventoryManager.add_stock_entry(stock_data):
            st.success("✅ Stock entry successful!")
            st.session_state.update({
                "stock_added": True,
                "reset_qr_gps": True,
                "entry_cycle": st.session_state["entry_cycle"] + 1
            })
            st.rerun()
        else:
            st.error("❌ Failed to add stock")

# ---------- Application Entry Point ----------
if __name__ == "__main__":
    app = InventoryApp()
    app.run()
