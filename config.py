import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    BASE_DIR = BASE_DIR
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'meditrack-pro-secret-key-2026-secure'
    
    # Database Mode
    DB_TYPE = os.environ.get('DB_TYPE', 'mysql')

    # MySQL Settings (Render / FreeDB)
    DB_TYPE = os.environ.get('DB_TYPE', 'mysql').strip().lower()
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'sql.freedb.tech').strip()
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT', '3306'))
    MYSQL_USER = os.environ.get('MYSQL_USER', 'u_LePDGb').strip()
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
    MYSQL_DB = os.environ.get('MYSQL_DB', 'freedb_cBl0YJ55').strip()

    # SQLite fallback path (if MySQL is stopped)
    DB_FOLDER = os.path.join(BASE_DIR, 'database')
    DATABASE_PATH = os.path.join(DB_FOLDER, 'pharmacy.db')
    SQLITE_PATH = os.path.join(DB_FOLDER, 'pharmacy.db')
    
    # Backups folder
    BACKUP_FOLDER = os.path.join(BASE_DIR, 'backups')
    
    # Invoices folder
    INVOICE_FOLDER = os.path.join(BASE_DIR, 'static', 'invoices')
    
    # Ensure directories exist
    os.makedirs(DB_FOLDER, exist_ok=True)
    os.makedirs(BACKUP_FOLDER, exist_ok=True)
    os.makedirs(INVOICE_FOLDER, exist_ok=True)
    
    # Pharmacy Details for Invoices & Branding
    PHARMACY_NAME = "MediTrack Pro Pharmacy"
    PHARMACY_TAGLINE = "Healthcare & Medicine Management"
    PHARMACY_ADDRESS = "Shop No. 12, Health Plaza, Medical Enclave, New Delhi - 110001"
    PHARMACY_PHONE = "+91 98765 43210"
    PHARMACY_EMAIL = "contact@meditrackpro.com"
    PHARMACY_GSTIN = "07AAAAA0000A1Z5"
    PHARMACY_DL_NO = "DL-20B/21B-45892"