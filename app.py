import os
import sys
import shutil
import sqlite3
import subprocess
from datetime import date, datetime, timedelta
from functools import wraps

# Auto-check and install dependencies if running directly
try:
    import flask
    import werkzeug
    import pymysql
except ImportError:
    print("=" * 60)
    print(" [MediTrack Pro Setup] Installing Flask, Werkzeug & PyMySQL...")
    print("=" * 60)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "flask", "werkzeug", "pymysql", "cryptography"])
    import flask
    import werkzeug
    import pymysql

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import check_password_hash

from dotenv import load_dotenv
load_dotenv()

from config import Config
from database import generate_password_hash, get_db_connection, init_db
from generate_assets import create_png


app = Flask(
    __name__,
    static_folder='static',
    static_url_path='/static'
)

app.config.from_object(Config)

# Auto generate placeholder assets if missing
def ensure_assets():
    img_dir = os.path.join(app.root_path, 'static', 'images')
    logo_path = os.path.join(img_dir, 'logo.png')
    pharma_path = os.path.join(img_dir, 'pharmacy.jpg')
    if not os.path.exists(logo_path):
        create_png(logo_path, 128, 128, 13, 148, 136)
    if not os.path.exists(pharma_path):
        create_png(pharma_path, 400, 300, 15, 118, 110)

ensure_assets()

# Inject common variables into all templates
@app.context_processor
def inject_pharmacy_info():
    return {
        'pharmacy_name': Config.PHARMACY_NAME,
        'pharmacy_tagline': Config.PHARMACY_TAGLINE,
        'pharmacy_phone': Config.PHARMACY_PHONE,
        'pharmacy_address': Config.PHARMACY_ADDRESS,
        'pharmacy_email': Config.PHARMACY_EMAIL,
        'pharmacy_gstin': Config.PHARMACY_GSTIN,
        'pharmacy_dl': Config.PHARMACY_DL_NO,
        'current_year': datetime.now().year,
        'current_user': session.get('user')
    }

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def verify_password(stored_password, provided_password):
    if stored_password == provided_password:
        return True
    try:
        return check_password_hash(stored_password, provided_password)
    except Exception:
        return False

# ----------------- AUTH ROUTES -----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and verify_password(user['password'], password):
            session['user'] = {
                'id': user['id'],
                'username': user['username'],
                'full_name': user['full_name'],
                'role': user['role']
            }
            flash(f"Welcome back, {user['full_name']}!", 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password. Please try again.', 'danger')

    return render_template('login.html')

@app.route('/change-password', methods=['POST'])
@login_required
def change_password():
    old_password = request.form.get('old_password', '').strip()
    new_password = request.form.get('new_password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()

    if not old_password or not new_password:
        flash('Please fill all password fields.', 'danger')
        return redirect(request.referrer or url_for('dashboard'))

    if new_password != confirm_password:
        flash('New password and confirm password do not match.', 'danger')
        return redirect(request.referrer or url_for('dashboard'))

    user_id = session['user']['id']
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

    if not user or not verify_password(user['password'], old_password):
        conn.close()
        flash('Current password is incorrect.', 'danger')
        return redirect(request.referrer or url_for('dashboard'))

    # Hash new password
    hashed = generate_password_hash(new_password)
    conn.execute('UPDATE users SET password = ? WHERE id = ?', (hashed, user_id))
    conn.commit()
    conn.close()

    flash('Password changed successfully!', 'success')
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

# ----------------- DASHBOARD -----------------
@app.route('/')
@login_required
def dashboard():
    conn = get_db_connection()
    today_str = datetime.now().strftime('%Y-%m-%d')
    month_str = datetime.now().strftime('%Y-%m')
    thirty_days_later = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

    # Metrics
    total_medicines = conn.execute('SELECT COUNT(*) as count FROM medicines').fetchone()['count']
    total_stock_qty = conn.execute('SELECT COALESCE(SUM(quantity), 0) as total FROM medicines').fetchone()['total']
    
    low_stock_count = conn.execute(
        'SELECT COUNT(*) as count FROM medicines WHERE quantity <= 10> 0'
    ).fetchone()['count']
    
    out_of_stock_count = conn.execute(
        'SELECT COUNT(*) as count FROM medicines WHERE quantity = 0'
    ).fetchone()['count']
    
    expired_count = conn.execute(
        'SELECT COUNT(*) as count FROM medicines WHERE expiry_date < ?', (today_str,)
    ).fetchone()['count']
    
    expiring_soon_count = conn.execute(
        'SELECT COUNT(*) as count FROM medicines WHERE expiry_date >= ? AND expiry_date <= ?',
        (today_str, thirty_days_later)
    ).fetchone()['count']

    # Today's Sales
    today_sales_data = conn.execute(
        'SELECT COALESCE(SUM(total_amount), 0) as total, COUNT(*) as count FROM sales WHERE DATE(created_at) = ?',
        (today_str,)
    ).fetchone()
    today_sales = today_sales_data['total']
    today_invoices = today_sales_data['count']

    # Monthly Sales
    month_sales = conn.execute(
        "SELECT COALESCE(SUM(total_amount), 0) as total FROM sales WHERE created_at LIKE ?",
        (f"{month_str}%",)
    ).fetchone()['total']

    # Recent Transactions
    recent_sales = conn.execute(
        'SELECT * FROM sales ORDER BY created_at DESC LIMIT 5'
    ).fetchall()

    # Low Stock Items Alert List
    low_stock_items = conn.execute(
        'SELECT * FROM medicines WHERE quantity <= min_stock ORDER BY quantity ASC LIMIT 6'
    ).fetchall()

    # Expiring Soon Items Alert List
    expiring_items = conn.execute(
       '''
    SELECT * FROM medicines
    WHERE expiry_date >= ?
      AND expiry_date <= ?
    ORDER BY expiry_date ASC
    LIMIT 6
    ''',
    (today_str, thirty_days_later)
    ).fetchall()

    # Sales Data for Last 7 Days (Chart)
    chart_labels = []
    chart_values = []
    for i in range(6, -1, -1):
        day = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        day_display = (datetime.now() - timedelta(days=i)).strftime('%d %b')
        chart_labels.append(day_display)
        val = conn.execute(
            'SELECT COALESCE(SUM(total_amount), 0) as total FROM sales WHERE DATE(created_at) = ?',
            (day,)
        ).fetchone()['total']
        chart_values.append(round(val, 2))

    conn.close()

    metrics = {
        'total_medicines': total_medicines,
        'total_stock_qty': total_stock_qty,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
        'expired_count': expired_count,
        'expiring_soon_count': expiring_soon_count,
        'today_sales': round(today_sales, 2),
        'today_invoices': today_invoices,
        'month_sales': round(month_sales, 2)
    }

    return render_template(
        'dashboard.html',
        metrics=metrics,
        recent_sales=recent_sales,
        low_stock_items=low_stock_items,
        expiring_items=expiring_items,
        chart_labels=chart_labels,
        chart_values=chart_values,
        today_str=today_str,
        thirty_days_later=thirty_days_later
    )

# ----------------- INVENTORY -----------------
@app.route('/inventory')
@login_required
def inventory():
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    status = request.args.get('status', '').strip()

    conn = get_db_connection()
    today_str = date.today()
    thirty_days_later = today_str + timedelta(days=30)

    query = 'SELECT * FROM medicines WHERE 1=1'
    params = []

    if search:
        query += ' AND (med_name LIKE ? OR batch_no LIKE ? OR supplier LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])

    if category:
        query += ' AND category = ?'
        params.append(category)

    if status == 'low':
        query += ' AND quantity <= min_stock AND quantity > 0'
    elif status == 'out':
        query += ' AND quantity = 0'
    elif status == 'expiring':
        query += ' AND expiry_date >= ? AND expiry_date <= ?'
        params.extend([today_str, thirty_days_later])
    elif status == 'expired':
        query += ' AND expiry_date < ?'
        params.append(today_str)

    query += ' ORDER BY med_name ASC'
    medicines = conn.execute(query, params).fetchall()

    # Get distinct categories for filter dropdown
    categories = [row['category'] for row in conn.execute('SELECT DISTINCT category FROM medicines ORDER BY category').fetchall()]
    conn.close()

    return render_template(
        'inventory.html',
        medicines=medicines,
        categories=categories,
        search=search,
        selected_category=category,
        selected_status=status,
        today_str=today_str,
        thirty_days_later=thirty_days_later
    )

@app.route('/inventory/add', methods=['POST'])
@login_required
def add_medicine():
    name = request.form.get('name', '').strip()
    category = request.form.get('category', '').strip()
    batch_no = request.form.get('batch_no', '').strip()
    expiry_date = request.form.get('expiry_date', '').strip()
    buy_price = float(request.form.get('buy_price', 0))
    sell_price = float(request.form.get('sell_price', 0))
    quantity = int(request.form.get('quantity', 0))
    min_stock = int(request.form.get('min_stock', 10))
    supplier = request.form.get('supplier', 'Generic Pharma').strip()

    if not name or not batch_no or not expiry_date:
        flash('Please fill in all required fields.', 'danger')
        return redirect(url_for('inventory'))

    conn = get_db_connection()
    conn.execute('''
        INSERT INTO medicines (med_name, category, batch_no, expiry_date, buy_price, sell_price, quantity, min_stock, supplier)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name, category, batch_no, expiry_date, buy_price, sell_price, quantity, min_stock, supplier))
    conn.commit()
    conn.close()

    flash(f'Medicine "{name}" added successfully!', 'success')
    return redirect(url_for('inventory'))

@app.route('/inventory/edit/<int:id>', methods=['POST'])
@login_required
def edit_medicine(id):
    name = request.form.get('name', '').strip()
    category = request.form.get('category', '').strip()
    batch_no = request.form.get('batch_no', '').strip()
    expiry_date = request.form.get('expiry_date', '').strip()
    buy_price = float(request.form.get('buy_price', 0))
    sell_price = float(request.form.get('sell_price', 0))
    quantity = int(request.form.get('quantity', 0))
    min_stock = int(request.form.get('min_stock', 10))
    supplier = request.form.get('supplier', '').strip()

    conn = get_db_connection()
    conn.execute('''
        UPDATE medicines 
        SET med_name = ?, category = ?, batch_no = ?, expiry_date = ?, buy_price = ?, sell_price = ?, quantity = ?, min_stock = ?, supplier = ?
        WHERE med_id = ?
    ''', (name, category, batch_no, expiry_date, buy_price, sell_price, quantity, min_stock, supplier, id))
    conn.commit()
    conn.close()

    flash(f'Medicine "{name}" updated successfully.', 'success')
    return redirect(url_for('inventory'))

@app.route('/inventory/delete/<int:id>', methods=['POST'])
@login_required
def delete_medicine(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM medicines WHERE med_id = ?', (id,))
    conn.commit()
    conn.close()

    flash('Medicine deleted successfully.', 'info')
    return redirect(url_for('inventory'))

# ----------------- BILLING / POS -----------------
@app.route('/billing')
@login_required
def billing():
    conn = get_db_connection()
    medicines = conn.execute('SELECT * FROM medicines WHERE quantity > 0 ORDER BY med_name ASC').fetchall()
    customers = conn.execute('SELECT * FROM customers ORDER BY name ASC').fetchall()
    conn.close()
    return render_template('billing.html', medicines=medicines, customers=customers)

@app.route('/billing/create', methods=['POST'])
@login_required
def create_sale():
    customer_id = request.form.get('customer_id')
    customer_name = request.form.get('customer_name', '').strip()
    customer_phone = request.form.get('customer_phone', '').strip()
    payment_mode = request.form.get('payment_mode', 'Cash')
    discount = float(request.form.get('discount', 0))
    tax_percent = float(request.form.get('tax_percent', 0))
    notes = request.form.get('notes', '')

    medicine_ids = request.form.getlist('medicine_id[]')
    quantities = request.form.getlist('quantity[]')

    if not medicine_ids:
        flash('Please add at least one medicine to the bill.', 'danger')
        return redirect(url_for('billing'))

    conn = get_db_connection()

    # Handle customer
    if customer_id and customer_id not in ('new', 'other'):
        cust = conn.execute('SELECT name FROM customers WHERE id = ?', (customer_id,)).fetchone()
        if cust:
            customer_name = cust['name']
    else:
        if not customer_name:
            customer_name = 'Walk-in Customer'
        # Add new customer if phone provided
        if customer_phone:
            try:
                cur = conn.execute('INSERT INTO customers (name, phone) VALUES (?, ?)', (customer_name, customer_phone))
                customer_id = cur.lastrowid
            except sqlite3.IntegrityError:
                cust = conn.execute('SELECT id FROM customers WHERE phone = ?', (customer_phone,)).fetchone()
                if cust:
                    customer_id = cust['id']

    # Calculate item totals & verify stock
    items_to_process = []
    subtotal = 0.0

    for m_id, q_val in zip(medicine_ids, quantities):
        qty = int(q_val)
        if qty <= 0:
            continue
        med = conn.execute('SELECT * FROM medicines WHERE med_id = ?', (m_id,)).fetchone()
        if not med:
            continue
        if med['quantity'] < qty:
            conn.close()
            flash(f"Insufficient stock for {med['med_name']}. Available: {med['quantity']}, Requested: {qty}", 'danger')
            return redirect(url_for('billing'))

        item_total = float(med['sell_price']) * qty
        subtotal += item_total
        items_to_process.append({
            'medicine_id': med['med_id'],
            'name': med['med_name'],
            'quantity': qty,
            'unit_price': med['sell_price'],
            'total_price': item_total
        })

    if not items_to_process:
        conn.close()
        flash('No valid items in the bill.', 'danger')
        return redirect(url_for('billing'))

    # Totals calculation
    tax_amount = round((subtotal - discount) * (tax_percent / 100.0), 2) if (subtotal - discount) > 0 else 0
    total_amount = round(subtotal - discount + tax_amount, 2)
    if total_amount < 0:
        total_amount = 0.0

    # Invoice number generator
    invoice_no = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # Insert Sale
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO sales (invoice_no, customer_id, customer_name, subtotal, discount, tax, total_amount, payment_mode, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (invoice_no, customer_id if customer_id and customer_id not in ('new', 'other') else None,
          customer_name, subtotal, discount, tax_amount, total_amount, payment_mode, notes))
    sale_id = cursor.lastrowid

    # Insert Sale Items & Deduct Inventory
    for item in items_to_process:
        cursor.execute('''
            INSERT INTO sale_items (sale_id, medicine_id, medicine_name, quantity, unit_price, total_price)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (sale_id, item['medicine_id'], item['name'], item['quantity'], item['unit_price'], item['total_price']))

        cursor.execute('''
            UPDATE medicines 
            SET quantity = quantity - ? 
            WHERE med_id = ?
        ''', (item['quantity'], item['medicine_id']))

    conn.commit()
    conn.close()

    flash(f'Invoice {invoice_no} generated successfully!', 'success')
    return redirect(url_for('view_invoice', sale_id=sale_id))

# ----------------- INVOICE -----------------
@app.route('/invoice/<int:sale_id>')
@login_required
def view_invoice(sale_id):
    conn = get_db_connection()
    sale = conn.execute('SELECT * FROM sales WHERE id = ?', (sale_id,)).fetchone()
    if not sale:
        conn.close()
        flash('Invoice not found.', 'danger')
        return redirect(url_for('dashboard'))

    items = conn.execute('''
        SELECT si.*, m.batch_no, m.expiry_date 
        FROM sale_items si 
        LEFT JOIN medicines m ON si.medicine_id = m.med_id 
        WHERE si.sale_id = ?
    ''', (sale_id,)).fetchall()

    customer = None
    if sale['customer_id']:
        customer = conn.execute('SELECT * FROM customers WHERE id = ?', (sale['customer_id'],)).fetchone()

    conn.close()
    
    return render_template(
    'invoice.html',
    sale=sale,
    items=items,
    customer=customer,
    pharmacy_name='SIDDH SHREE KHEMA BABA PHARMACY',
    pharmacy_tagline='Pharmacy & Healthcare',
    pharmacy_address='𝗔𝗱𝗱𝗿𝗲𝘀𝘀: Siddh Shree Khema Baba Mandir Ke Samne,Baytu,Barmer(344034),Rajasthan,India',
    pharmacy_phone='+91 6376223233',
    pharmacy_email='mkjaat084@gmail.com',
    pharmacy_gstin='Apna valid GSTIN',
    pharmacy_dl='Apna valid Drug Licence Number')

# ----------------- SALES HISTORY -----------------
@app.route('/sales-history')
@login_required
def sales_history():
    search = request.args.get('search', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()

    conn = get_db_connection()
    query = 'SELECT * FROM sales WHERE 1=1'
    params = []

    if search:
        query += ' AND (invoice_no LIKE ? OR customer_name LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%'])

    if start_date:
        query += ' AND DATE(created_at) >= ?'
        params.append(start_date)

    if end_date:
        query += ' AND DATE(created_at) <= ?'
        params.append(end_date)

    query += ' ORDER BY created_at DESC'
    sales = conn.execute(query, params).fetchall()

    total_revenue = sum(s['total_amount'] for s in sales)
    conn.close()

    return render_template(
        'sales_history.html',
        sales=sales,
        total_revenue=round(total_revenue, 2),
        search=search,
        start_date=start_date,
        end_date=end_date
    )

# ----------------- CUSTOMERS -----------------
@app.route('/customers')
@login_required
def customers():
    search = request.args.get('search', '').strip()
    conn = get_db_connection()

    query = '''
        SELECT c.*, 
               COUNT(s.id) as total_invoices, 
               COALESCE(SUM(s.total_amount), 0) as total_spent
        FROM customers c
        LEFT JOIN sales s ON c.id = s.customer_id
        WHERE 1=1
    '''
    params = []

    if search:
        query += ' AND (c.name LIKE ? OR c.phone LIKE ? OR c.email LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])

    query += ' GROUP BY c.id ORDER BY total_spent DESC'
    customers_list = conn.execute(query, params).fetchall()
    conn.close()

    return render_template('customers.html', customers=customers_list, search=search)

@app.route('/customers/add', methods=['POST'])
@login_required
def add_customer():
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    address = request.form.get('address', '').strip()

    if not name:
        flash('Customer name is required.', 'danger')
        return redirect(url_for('customers'))

    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO customers (name, phone, email, address) VALUES (?, ?, ?, ?)',
                     (name, phone, email, address))
        conn.commit()
        flash(f'Customer "{name}" added successfully!', 'success')
    except sqlite3.IntegrityError:
        flash(f'A customer with phone number "{phone}" already exists.', 'warning')
    finally:
        conn.close()

    return redirect(url_for('customers'))


# ----------------- EDIT CUSTOMER -----------------

@app.route('/customers/edit/<int:id>', methods=['POST'])
@login_required
def edit_customer(id):
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    address = request.form.get('address', '').strip()

    if not name:
        flash('Customer name is required.', 'danger')
        return redirect(url_for('customers'))

    conn = get_db_connection()

    try:
        customer = conn.execute(
            'SELECT id FROM customers WHERE id = ?', (id,)
        ).fetchone()

        if not customer:
            flash('Customer not found.', 'danger')
            return redirect(url_for('customers'))

        conn.execute(
            '''UPDATE customers
               SET name = ?, phone = ?, email = ?, address = ?
               WHERE id = ?''',
            (name, phone, email, address, id)
        )
        conn.commit()
        flash(f'Customer "{name}" updated successfully.', 'success')

    except Exception:
        conn.rollback()
        flash('Could not update customer. Check whether the phone number is already used.', 'danger')

    finally:
        conn.close()

    return redirect(url_for('customers'))


# ----------------- DELETE CUSTOMER -----------------

@app.route('/customers/delete/<int:id>', methods=['POST'])
@login_required
def delete_customer(id):
    conn = get_db_connection()

    try:
        customer = conn.execute(
            'SELECT id, name FROM customers WHERE id = ?', (id,)
        ).fetchone()

        if not customer:
            flash('Customer not found.', 'danger')
            return redirect(url_for('customers'))

        # Preserve customers linked to existing invoices
        invoices = conn.execute(
            'SELECT COUNT(*) AS total FROM sales WHERE customer_id = ?',
            (id,)
        ).fetchone()

        if invoices and invoices['total'] > 0:
            flash(
                'This customer has existing invoices and cannot be deleted. '
                'Edit the customer details instead.',
                'warning'
            )
            return redirect(url_for('customers'))

        conn.execute('DELETE FROM customers WHERE id = ?', (id,))
        conn.commit()
        flash('Customer deleted successfully.', 'success')

    except Exception:
        conn.rollback()
        flash('Customer could not be deleted.', 'danger')

    finally:
        conn.close()

    return redirect(url_for('customers'))

# ----------------- REPORTS -----------------
@app.route('/reports')
@login_required
def reports():
    conn = get_db_connection()
    today_str = datetime.now().strftime('%Y-%m-%d')
    month_str = datetime.now().strftime('%Y-%m')

    # Overall Summary
    total_revenue = conn.execute('SELECT COALESCE(SUM(total_amount), 0) as total FROM sales').fetchone()['total']
    total_sales_count = conn.execute('SELECT COUNT(*) as count FROM sales').fetchone()['count']
    
    # Stock Valuation
    stock_val = conn.execute('''
        SELECT 
            COALESCE(SUM(buy_price * quantity), 0) as total_cost_value,
            COALESCE(SUM(sell_price * quantity), 0) as total_retail_value,
            COALESCE(SUM(quantity), 0) as total_units
        FROM medicines
    ''').fetchone()

    # Top 5 Best Selling Medicines
    top_selling = conn.execute('''
        SELECT medicine_name, SUM(quantity) as total_qty, SUM(total_price) as total_amount
        FROM sale_items
        GROUP BY medicine_name
        ORDER BY total_qty DESC
        LIMIT 5
    ''').fetchall()

    # Category Wise Stock & Value
    category_summary = conn.execute('''
        SELECT category, COUNT(*) as count, SUM(quantity) as total_units, SUM(sell_price * quantity) as retail_val
        FROM medicines
        GROUP BY category
        ORDER BY count DESC
    ''').fetchall()

    # Profit Estimation (Revenue minus Wholesale cost of items sold)
    profit_data = conn.execute('''
        SELECT 
            COALESCE(SUM(si.total_price), 0) as sales_val,
            COALESCE(SUM(si.quantity * m.buy_price), 0) as cost_val
        FROM sale_items si
        LEFT JOIN medicines m ON si.medicine_id = m.med_id
    ''').fetchone()
    
    estimated_profit = round(profit_data['sales_val'] - profit_data['cost_val'], 2)

    conn.close()

    report_metrics = {
        'total_revenue': round(total_revenue, 2),
        'total_sales_count': total_sales_count,
        'total_cost_value': round(stock_val['total_cost_value'], 2),
        'total_retail_value': round(stock_val['total_retail_value'], 2),
        'total_units': stock_val['total_units'],
        'estimated_profit': estimated_profit
    }

    return render_template(
        'reports.html',
        metrics=report_metrics,
        top_selling=top_selling,
        category_summary=category_summary
    )


# ----------------- BACKUP -----------------
@app.route('/backup')
@login_required
def backup_database():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"pharmacy_backup_{timestamp}.sql"
    dest_path = os.path.join(Config.BACKUP_FOLDER, backup_filename)

    try:
        # Create backup folder if it does not exist
        os.makedirs(Config.BACKUP_FOLDER, exist_ok=True)

        if getattr(Config, 'DB_TYPE', 'mysql').lower() == 'mysql':
            conn = get_db_connection()
            try:
                cursor = conn.cursor()

                with open(dest_path, 'w', encoding='utf-8') as backup_file:
                    cursor.execute("SHOW TABLES")
                    tables = cursor.fetchall()

                    if not tables:
                        raise RuntimeError("MySQL database has no tables to back up.")

                    for row in tables:
                        table_name = next(iter(row.values()))
                        safe_table = '`' + str(table_name).replace('`', '``') + '`'

                        cursor.execute(f"SHOW CREATE TABLE {safe_table}")
                        create_row = cursor.fetchone()
                        create_sql = list(create_row.values())[1]

                        backup_file.write(f"\nDROP TABLE IF EXISTS {safe_table};\n")
                        backup_file.write(create_sql + ";\n\n")

                        cursor.execute(f"SELECT * FROM {safe_table}")
                        rows = cursor.fetchall()

                        for record in rows:
                            columns = ', '.join(
                                '`' + str(col).replace('`', '``') + '`'
                                for col in record.keys()
                            )
                            values = []
                            for value in record.values():
                                if value is None:
                                    values.append("NULL")
                                elif isinstance(value, (int, float)):
                                    values.append(str(value))
                                elif isinstance(value, (bytes, bytearray)):
                                    values.append("0x" + value.hex())
                                else:
                                    escaped = str(value).replace("\\", "\\\\").replace("'", "\\'")
                                    values.append("'" + escaped + "'")

                            backup_file.write(
                                f"INSERT INTO {safe_table} ({columns}) "
                                f"VALUES ({', '.join(values)});\n"
                            )
            finally:
                conn.close()

        else:
            sqlite_path = getattr(
                Config, 'SQLITE_PATH',
                getattr(Config, 'DATABASE_PATH', 'pharmacy.db')
            )
            if not os.path.exists(sqlite_path):
                raise FileNotFoundError("SQLite database file was not found.")

            shutil.copy2(sqlite_path, dest_path.replace('.sql', '.db'))
            backup_filename = backup_filename.replace('.sql', '.db')

        flash(f"Database backup created: {backup_filename}", "success")

    except Exception as e:
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except OSError:
                pass
        flash(f"Backup failed: {e}", "danger")

    return redirect(url_for('dashboard'))


# ----------------- MAIN RUNNER -----------------
if __name__ == '__main__':
    print("=" * 60)
    print(" MediTrack Pro - Pharmacy & Healthcare Management System")
    print("=" * 60)
    print(" Application running at: http://127.0.0.1:5000")
    print("=" * 60)

    app.run(debug=False, port=5000)
