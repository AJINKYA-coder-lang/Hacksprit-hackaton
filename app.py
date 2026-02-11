import os
import csv
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder='.')
app.config['SECRET_KEY'] = 'your-secret-key-here' 

# Use /tmp for SQLite on Vercel because the root is read-only
if os.environ.get('VERCEL'):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/users.db'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(1000))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create the database tables
with app.app_context():
    db.create_all()

@app.route('/')
@login_required
def index():
    # Calculate global stats for the dashboard charts
    total_consumption = 0
    power_saved = 0
    event_data = [] # Usage on weekends or spikes
    daily_consumption = {} # Date: total_kWh
    
    try:
        with open('consuption.csv', 'r') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                val = float(row['Total_Energy_kWh'])
                total_consumption += val
                
                date = row['Date']
                daily_consumption[date] = daily_consumption.get(date, 0) + val
                
                # Assume events happen on weekends or when Is_Weekend is '1'
                if row['Is_Weekend'] == '1':
                    event_data.append(val)
        
        # Power saved estimate (10% of total as a mock 'efficiency' win)
        power_saved = total_consumption * 0.12 
        
        # Get last 7 days for the "Total Consumption" trend
        sorted_dates = sorted(daily_consumption.keys())[-7:]
        consumption_trend = [daily_consumption[d] for d in sorted_dates]
        
    except Exception as e:
        print(f"Error calculating global stats: {e}")
        consumption_trend = []
        sorted_dates = []

    return render_template('index.html', 
                           user=current_user, 
                           total=f"{total_consumption:,.0f}",
                           saved=f"{power_saved:,.0f}",
                           trend_labels=sorted_dates,
                           trend_values=consumption_trend)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password, password):
            flash('Please check your login details and try again.')
            return redirect(url_for('login'))

        login_user(user, remember=remember)
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        name = request.form.get('name')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if user:
            flash('Email address already exists')
            return redirect(url_for('signup'))

        new_user = User(email=email, name=name, password=generate_password_hash(password, method='pbkdf2:sha256'))
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/predict')
@login_required
def predict_hub():
    return render_template('comments.html')

@app.route('/prediction_input', methods=['GET', 'POST'])
@login_required
def prediction_input():
    if request.method == 'POST':
        try:
            building_id = request.form.get('building_id')
            temperature = float(request.form.get('temperature', 30))
            is_weekend = 1 if request.form.get('is_weekend') else 0
            num_devices = int(request.form.get('num_devices', 10))
            avg_power = float(request.form.get('avg_power', 0.5))
            num_events = int(request.form.get('num_events', 2))
            
            base_load = num_devices * avg_power * 8
            temp_factor = (temperature - 20) * 5 if temperature > 20 else 0
            event_load = num_events * 25
            
            prediction = base_load + temp_factor + event_load
            if is_weekend == 1 and num_events == 0:
                prediction *= 0.7
                
            return render_template('prediction.html', 
                                 prediction=f"{prediction:.2f}", 
                                 building_id=building_id)
        except Exception as e:
            return render_template('predict_form.html', error=f"Calculation Error: {str(e)}")
            
    return render_template('predict_form.html')

@app.route('/visualize')
@login_required
def visualize():
    building_totals = {'1': 0, '2': 0, '3': 0}
    temp_data = [] 
    weekend_sum = 0
    weekend_count = 0
    weekday_sum = 0
    weekday_count = 0
    
    try:
        with open('consuption.csv', 'r') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                uid = row['Building_ID']
                val = float(row['Total_Energy_kWh'])
                temp = float(row['Temperature_C'])
                is_weekend = row['Is_Weekend'] == '1'
                
                if uid in building_totals:
                    building_totals[uid] += val
                
                temp_data.append({'x': temp, 'y': val})
                
                if is_weekend:
                    weekend_sum += val
                    weekend_count += 1
                else:
                    weekday_sum += val
                    weekday_count += 1
                    
    except Exception as e:
        print(f"Viz error: {e}")

    avg_weekend = weekend_sum / weekend_count if weekend_count > 0 else 0
    avg_weekday = weekday_sum / weekday_count if weekday_count > 0 else 0

    return render_template('visualize.html', 
                          building_labels=['Admin', 'CSE', 'Production'],
                          building_values=[building_totals['1'], building_totals['2'], building_totals['3']],
                          temp_scatter=temp_data[:100],
                          comparison_labels=['Weekday Avg', 'Weekend Avg'],
                          comparison_values=[avg_weekday, avg_weekend]
                          )

@app.route('/suggestions', methods=['GET', 'POST'])
@login_required
def suggestions():
    if request.method == 'POST':
        building_id = request.form.get('building_id')
        suggestions_list = []
        
        try:
            building_data = []
            with open('consuption.csv', 'r') as f:
                reader = csv.DictReader(f, delimiter='\t')
                for row in reader:
                    if row['Building_ID'] == building_id:
                        building_data.append(row)
            
            if building_data:
                # 1. Analyze for high temperature correlations
                high_temp_days = [float(r['Total_Energy_kWh']) for r in building_data if float(r['Temperature_C']) > 32]
                avg_usage = sum(float(r['Total_Energy_kWh']) for r in building_data) / len(building_data)
                
                # Check for HVAC optimization
                if high_temp_days:
                    avg_high_temp = sum(high_temp_days) / len(high_temp_days)
                    if avg_high_temp > avg_usage * 1.2:
                        suggestions_list.append({
                            'Suggestion': 'Optimize AC/HVAC thermostat settings during heat waves to avoid peak load spikes.',
                            'Potential_Savings_kWh': f"{int(avg_high_temp * 0.15)}",
                            'Priority': 'High'
                        })

                # 2. Analyze Weekend usage
                weekend_usage = [float(r['Total_Energy_kWh']) for r in building_data if r['Is_Weekend'] == '1']
                weekday_usage = [float(r['Total_Energy_kWh']) for r in building_data if r['Is_Weekend'] == '0']
                
                if weekend_usage and weekday_usage:
                    avg_weekend = sum(weekend_usage) / len(weekend_usage)
                    avg_weekday = sum(weekday_usage) / len(weekday_usage)
                    
                    # If weekend stays high, suspect unused equipment
                    if avg_weekend > avg_weekday * 0.6:
                        suggestions_list.append({
                            'Suggestion': 'Implement a "Smarter Power-Down" policy. Weekend consumption is unexpectedly high compared to weekdays.',
                            'Potential_Savings_kWh': f"{int(avg_weekend * 0.3)}",
                            'Priority': 'Medium'
                        })

                # 3. General Efficiency Suggestion
                if avg_usage > 600:
                    suggestions_list.append({
                        'Suggestion': 'Upgrade to Motion-Sensed LED Lighting. High baseline consumption detected.',
                        'Potential_Savings_kWh': f"{int(avg_usage * 0.12)}",
                        'Priority': 'Medium'
                    })
                
                # 4. Critical Surge Check
                if any(float(r['Total_Energy_kWh']) > avg_usage * 1.5 for r in building_data):
                    suggestions_list.append({
                        'Suggestion': 'Inspect electrical systems for phantom loads or faulty equipment causing irregular power surges.',
                        'Potential_Savings_kWh': 'Variable',
                        'Priority': 'High'
                    })

            if not suggestions_list:
                suggestions_list.append({'Suggestion': 'Keep maintaining current efficiency. No major anomalies detected.', 'Potential_Savings_kWh': '0', 'Priority': 'Low'})

        except Exception as e:
            print(f"Suggestions error: {e}")
            suggestions_list = [{'Suggestion': 'Error analyzing data. Check back later.', 'Potential_Savings_kWh': 'N/A', 'Priority': 'Low'}]

        return render_template('suggestion.html', building_id=building_id, suggestions=suggestions_list)
        
    return render_template('suggestion_form.html')

@app.route('/add_components')
@login_required
def add_components():
    return render_template('desktop new.html', user=current_user)

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)



@app.route('/department/<name>')
@login_required
def department_detail(name):
    name_to_id = {
        'adminPage': '1',
        'csePage': '2',
        'productionPage': '3',
        'mechanicalPage': '4'
    }
    
    building_id = name_to_id.get(name)
    dept_title = name.replace('Page', '').capitalize() + ' Department'
    
    usage = "0 kWh"
    efficiency = "N/A"
    last_update = "N/A"
    historical_labels = []
    historical_values = []
    
    try:
        data_rows = []
        with open('consuption.csv', 'r') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                if row['Building_ID'] == building_id:
                    data_rows.append(row)
        
        if data_rows:
            # Get latest 10 days for graph
            graph_rows = data_rows[-10:]
            historical_labels = [r['Date'] for r in graph_rows]
            historical_values = [float(r['Total_Energy_kWh']) for r in graph_rows]

            latest = data_rows[-1]
            usage = f"{float(latest['Total_Energy_kWh']):.2f} kWh"
            last_update = latest['Date']
            
            all_usages = [float(r['Total_Energy_kWh']) for r in data_rows]
            avg_usage = sum(all_usages) / len(all_usages)
            current_val = float(latest['Total_Energy_kWh'])
            eff_val = min(100, (avg_usage / current_val) * 100) if current_val > 0 else 0
            efficiency = f"{int(eff_val)}%"
            
    except Exception as e:
        print(f"Error reading CSV: {e}")

    data = {
        'id': building_id,
        'title': dept_title,
        'usage': usage,
        'efficiency': efficiency,
        'last_update': last_update,
        'graph_labels': historical_labels,
        'graph_values': historical_values
    }
    return render_template('department.html', dept=data, user=current_user)

@app.route('/log_consumption', methods=['POST'])
@login_required
def log_consumption():
    building_id = request.form.get('building_id')
    energy = request.form.get('energy_value')
    temp = request.form.get('temp', '25')
    date = request.form.get('date')
    
    if not building_id or not energy or not date:
        flash('Please fill all fields')
        return redirect(url_for('index'))

    try:
        with open('consuption.csv', 'a', newline='') as f:
            # Append new record with tab delimiter to match existing format
            f.write(f"\n{building_id}\t{date}\t{energy}\t{temp}\t0")
        flash('Data logged successfully!')
    except Exception as e:
        flash(f'Error logging data: {e}')
        
    return redirect(url_for('index'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
