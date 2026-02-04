from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__, template_folder='.')

@app.route('/')
def index():
    user = {'email': 'admin@example.com'}
    return render_template('index.html', user=user)

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/predict')
def predict_page():
    return render_template('comments.html')

@app.route('/predict_form')
def predict_form():
    # Placeholder for the actual prediction form if it's a separate file
    # Based on file list, "predict form" might be a file but let's check its content
    return render_template('prediction.html', building_id=1, prediction=250.5)

@app.route('/visualize')
def visualize():
    return render_template('visualize.html')

@app.route('/suggestions', methods=['GET', 'POST'])
def suggestions():
    if request.method == 'POST':
        building_id = request.form.get('building_id')
        dummy_suggestions = [
            {'Suggestion': 'Install LED lighting', 'Potential_Savings_kWh': 50, 'Priority': 'High'},
            {'Suggestion': 'Optimize HVAC schedule', 'Potential_Savings_kWh': 120, 'Priority': 'Medium'},
            {'Suggestion': 'Improve insulation', 'Potential_Savings_kWh': 30, 'Priority': 'Low'}
        ]
        return render_template('suggestion.html', building_id=building_id, suggestions=dummy_suggestions)
    return render_template('suggestion form.html')

@app.route('/add_components')
def add_components():
    user = {'email': 'admin@example.com'}
    return render_template('desktop new.html', user=user)

@app.route('/logout')
def logout():
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
