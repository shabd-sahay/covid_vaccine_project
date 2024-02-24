from flask import Flask, render_template, request, redirect, url_for, session
import pymysql
from datetime import datetime, timedelta
import re
import schedule
import time
import configparser

app = Flask(__name__)

# Connect to the MySQL database
connection = pymysql.connect(
    host='localhost',
    user='root',
    password='Shabd@2003..',
    database='covid_project',
    cursorclass=pymysql.cursors.DictCursor
)

# Function to update availability

max_initial_slots = 10
def num_centers():
    try:
        with connection.cursor() as cursor:
            sql = "SELECT COUNT(*) AS num_centers FROM `centers`"
            cursor.execute(sql)
            result = cursor.fetchone()
            num_centers = result['num_centers']
            return num_centers
    except pymysql.Error as e:
        print(str(e))
        return None


def update_availability():
    try:
        with connection.cursor() as cursor:
            # Get the current date
            today = datetime.now().date()

            # Loop through each center
            for center_id in range(1, num_centers + 1):  
                # Get the bookings for the center for the present day and the next two days
                for i in range(3):
                    date = today + timedelta(days=i)
                    sql = "SELECT SUM(`doses_booked`) AS `total_booked` FROM `dosage_details` WHERE `center_id`=%s AND `date`=%s"
                    cursor.execute(sql, (center_id, date))
                    result = cursor.fetchone()
                    total_booked = result['total_booked'] if result['total_booked'] else 0

                    # Update the available slots for the center for the current date
                    available_slots = max_initial_slots - total_booked  
                    update_sql = "UPDATE `dosage_details` SET `slots_available`=%s WHERE `center_id`=%s AND `date`=%s"
                    cursor.execute(update_sql, (available_slots, center_id, date))
                    
            connection.commit()
            print("Availability updated successfully")
    except pymysql.Error as e:
        print(str(e))

# Schedule the update_availability function to run every day at a specific time
schedule.every().day.at("06:00").do(update_availability)



# Validation for Email
email_pattern = r'^[\w\.-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$'
def validate_email(email):
    return re.match(email_pattern, email)

# Validation for Password
def validate_password(password):
    # Password should be at least 8 characters long and contain at least one digit and one special character
    if len(password) < 8:
        return False
    if not any(char.isdigit() for char in password):
        return False
    if not any(char.isalpha() for char in password):
        return False
    return True
# Routes

#login
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            with connection.cursor() as cursor:
                sql = "SELECT * FROM `users` WHERE `username`=%s AND `password`=%s"
                cursor.execute(sql, (username, password))
                user = cursor.fetchone()
                if user:
                    session['user_id'] = user['id']
                    if user['is_admin'] == 1:
                        return redirect(url_for('admin_dashboard'))
                    else:
                        return redirect(url_for('user_dashboard'))
                else:
                    return render_template('index.html', error="*Invalid username or password")
        except pymysql.Error as e:
            return str(e)
        
    return render_template('index.html')


#register
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        email_error = None
        password_error = None
        
        # Validate email
        if not validate_email(email):
            email_error = "*Invalid email address"
        
        # Validate password
        if not validate_password(password):
            password_error = "*Invalid password"
        
        if email_error or password_error:
            return render_template('register.html', email_error=email_error, password_error=password_error)
        
        

        try:
            with connection.cursor() as cursor:
                sql = "INSERT INTO `users` (`username`, `email`, `password`,`is_admin`) VALUES (%s, %s, %s, 0)"
                cursor.execute(sql, (username, email, password))
                connection.commit()
                return redirect(url_for('login'))
        except pymysql.Error as e:
            return str(e)
        
    return render_template('register.html')

#if the user is admin
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        with connection.cursor() as cursor:
            sql = "SELECT * FROM `centers`"
            cursor.execute(sql)
            centers = cursor.fetchall()
        return render_template('admin_dashboard.html', centers=centers)
    except pymysql.Error as e:
        return str(e)

@app.route('/add_center', methods=['GET', 'POST'])
def add_center():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form['name']
        city = request.form['city']
        working_hours = request.form['working_hours']
        initial_slots = 10  # Initial number of slots
        
        try:
            with connection.cursor() as cursor:
                # Insert into centers table
                center_sql = "INSERT INTO `centers` (`name`, `city`, `working_hours`) VALUES (%s, %s, %s)"
                cursor.execute(center_sql, (name, city, working_hours))
                connection.commit()
                
                center_id = cursor.lastrowid  # Get the ID of the inserted center
                
                # Insert into dosage_details table for each day with initial slots
                today = datetime.now().date()
                for i in range(3):  # Insert dosage details for the next 3 days
                    date = today + timedelta(days=i)
                    dosage_sql = "INSERT INTO `dosage_details` (`center_id`, `date`, `doses_booked`) VALUES (%s,%s, %s)"
                    cursor.execute(dosage_sql, (center_id, date, initial_slots))
                    connection.commit()
                
                return redirect(url_for('admin_dashboard'))
        except pymysql.Error as e:
            return str(e)
        
    return render_template('add_center.html')

@app.route('/get_dosage_details')
def get_dosage_details():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        with connection.cursor() as cursor:
            # Retrieve center details and dosage details using a SQL JOIN
            sql = """
            SELECT 
                c.id AS center_id,
                c.name AS center_name,
                c.city AS center_city,
                SUM(d.doses_booked) AS total_doses_booked
            FROM 
                centers c
            INNER JOIN 
                dosage_details d ON c.id = d.center_id
            GROUP BY 
                c.id, c.name, c.city
            """
            cursor.execute(sql)
            dosage_details = cursor.fetchall()
            
        return render_template('dosage_details_grouped.html', dosage_details=dosage_details)
    except pymysql.Error as e:
        return str(e)


@app.route('/dosage_details/<int:center_id>', methods=['GET', 'POST'])
def dosage_details(center_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        with connection.cursor() as cursor:
            # Retrieve center details
            center_sql = "SELECT * FROM `centers` WHERE `id` = %s"
            cursor.execute(center_sql, center_id)
            center = cursor.fetchone()
            
            if not center:
                return "Center not found"
            
            # Retrieve dosage details for the specified center
            dosage_sql = "SELECT `date`, `doses_booked` FROM `dosage_details` WHERE `center_id` = %s"
            cursor.execute(dosage_sql, center_id)
            dosage_details = cursor.fetchall()
            
        return render_template('center_details.html', center=center, dosage_details=dosage_details)
    except pymysql.Error as e:
        return str(e)

@app.route('/delete_center/<int:center_id>', methods=['POST'])
def delete_center(center_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        with connection.cursor() as cursor:
            # Delete record from dosage_details table
            delete_dosage_sql = "DELETE FROM `dosage_details` WHERE `center_id` = %s"
            cursor.execute(delete_dosage_sql, center_id)
            
            # Delete related record from centers table
            delete_center_sql = "DELETE FROM `centers` WHERE `id` = %s"
            cursor.execute(delete_center_sql, center_id)
            
            connection.commit()
            
            return redirect(url_for('admin_dashboard'))
    except pymysql.Error as e:
        return str(e)

#if the login credentials are not of the admin(user)

@app.route('/user_dashboard', methods=['GET', 'POST'])
def user_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get today's date
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    day_after_tomorrow = today + timedelta(days=2)
    
    try:
        with connection.cursor() as cursor:
            # Your SQL query to retrieve data based on today, tomorrow, and day after tomorrow
            sql = """
            SELECT 
                `centers`.`id` AS center_id,
                `centers`.`city`, 
                `centers`.`name`, 
                `dosage_details`.`date`, 
                `dosage_details`.`doses_booked` 
            FROM 
                `centers` 
            INNER JOIN 
                `dosage_details` 
            ON 
                `centers`.`id` = `dosage_details`.`center_id` 
            WHERE 
                `date` IN (%s, %s, %s)
            """
            cursor.execute(sql, (today, tomorrow, day_after_tomorrow))
            centers_data = {}
            for row in cursor.fetchall():
                center_id = row['center_id']
                if center_id not in centers_data:
                    centers_data[center_id] = {
                        'city': row['city'],
                        'name': row['name'],
                        'slots': {
                            today: 0,
                            tomorrow: 0,
                            day_after_tomorrow: 0
                        }
                    }
                centers_data[center_id]['slots'][row['date']] = row['doses_booked']
            
        return render_template('user_dashboard.html', centers_data=centers_data, today=today, tomorrow=tomorrow, day_after_tomorrow=day_after_tomorrow)
    
    except pymysql.Error as e:
        return str(e)

@app.route('/apply', methods=['POST'])
def apply():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    center_id = request.form.get('center_id')
    date = request.form.get('date')
    
    try:
        with connection.cursor() as cursor:
            sql = "UPDATE `dosage_details` SET `doses_booked` = `doses_booked` - 1 WHERE `center_id` = %s AND `date` = %s"
            cursor.execute(sql, (center_id, date))
            connection.commit()
            
            return redirect(url_for('user_dashboard'))  # Redirect to the user dashboard after applying for the slot
    except pymysql.Error as e:
        return str(e)

@app.route('/search', methods=['POST'])
def search():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    search_query = request.form.get('search_query')
    
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    day_after_tomorrow = today + timedelta(days=2)
    try:
        with connection.cursor() as cursor:
            # Your SQL query to search for vaccination centers
            sql = """
            SELECT 
                `centers`.`id` AS center_id,
                `centers`.`city`, 
                `centers`.`name`, 
                `dosage_details`.`date`, 
                `dosage_details`.`doses_booked` 
            FROM 
                `centers` 
            INNER JOIN 
                `dosage_details` 
            ON 
                `centers`.`id` = `dosage_details`.`center_id` 
            WHERE 
                `centers`.`name` LIKE %s OR
                `centers`.`city` LIKE %s
            """
            cursor.execute(sql, (f'%{search_query}%', f'%{search_query}%'))
            centers_data = {}
            for row in cursor.fetchall():
                center_id = row['center_id']
                if center_id not in centers_data:
                    centers_data[center_id] = {
                        'city': row['city'],
                        'name': row['name'],
                        'slots': {
                            today: 0,
                            tomorrow: 0,
                            day_after_tomorrow: 0
                        }
                    }
                centers_data[center_id]['slots'][row['date']] = row['doses_booked']

        return render_template('user_dashboard.html', centers_data=centers_data, today=today, tomorrow=tomorrow, day_after_tomorrow=day_after_tomorrow)
    except pymysql.Error as e:
        return str(e)
    
    
#logout funtionality for both user and admin
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.secret_key = 'your_secret_key'
    app.run(debug=True)
