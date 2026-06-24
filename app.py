from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import InputRequired
from datetime import datetime
from os import environ
from converter import celsius_to_fahrenheit

app = Flask(__name__)
# Configure secret key for flask - used for session sharing
app.config['SECRET_KEY'] = 'your-secret-key'

# Configure database details, these need to be changed depending on how you configured mysql container
db_user = environ.get('DB_USER', 'CHANGEME')
db_pass = environ.get('DB_PASS', 'CHANGEME')
db_host = environ.get('DB_HOST', 'CHANGEME')
db_name = environ.get('DB_NAME', 'CHANGEME')

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://'+db_user+':'+db_pass+'@'+db_host+'/'+db_name
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

student = environ.get('STUDENT', 'Default Student')
college = environ.get('COLLEGE', 'Default College')

db = SQLAlchemy(app)

class Temperature(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    celsius = db.Column(db.Float, nullable=False)
    fahrenheit = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(20), nullable=False)
    user_agent = db.Column(db.String(200), nullable=False)

with app.app_context():
    db.create_all()

class TemperatureForm(FlaskForm):
    celsius = StringField('Celsius', validators=[InputRequired()])
    submit = SubmitField('Convert')

@app.route('/', methods=['GET', 'POST'])
def index():
    form = TemperatureForm()
    if form.validate_on_submit():
        celsius = float(form.celsius.data)
        fahrenheit = celsius_to_fahrenheit(celsius)
        temperature = Temperature(celsius=celsius, fahrenheit=fahrenheit, ip_address=request.remote_addr, user_agent=request.user_agent.string)
        db.session.add(temperature)
        db.session.commit()
    temperatures = Temperature.query.order_by(Temperature.date.desc()).limit(10).all()
    # log_entries = [(t.fahrenheit, t.ip_address, t.user_agent.split()[0], t.date.strftime('%m/%d/%Y %I:%M:%S %p')) for t in temperatures]
    log_entries = [(t.date.strftime('%m/%d/%Y %I:%M:%S %p'), t.celsius, t.fahrenheit, t.ip_address, t.user_agent.split()[0], ) for t in temperatures]
    return render_template('index.html', form=form, log_entries=log_entries, student=student, college=college)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
