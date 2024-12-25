from datetime import datetime, timezone
from flask import Flask, render_template, request, url_for, redirect, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from sqlalchemy import func




app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite"
app.config["SECRET_KEY"] = "root"
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)

class Users(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)

class Cash(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    reason = db.Column(db.String(250))
    date = db.Column(db.DateTime, default=datetime.now(timezone.utc))  # Automatically set date on creation
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('Users', backref=db.backref('cash_entries', lazy=True))

class Expenses(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.now(timezone.utc))  # Use timezone-aware UTC
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('Users', backref=db.backref('expenses', lazy=True))
with app.app_context():
    db.create_all()


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Users, int(user_id))

@app.route("/", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        user = Users.query.filter_by(username=request.form.get("username")).first()
        if user and user.password == request.form.get("password"):
            login_user(user)
            return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", error="Invalid username or password.")
    return render_template("login.html")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")

        # Check if username already exists
        if Users.query.filter_by(username=username).first():
            flash("Username already exists. Please choose a different one.")
            return redirect(url_for("register"))

        # Create new user
        new_user = Users(username=username, password=password)  # Note: Consider hashing passwords!
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route('/addcash', methods=['GET', 'POST'])
@login_required
def add_cash():
    if request.method == 'POST':
        amount = request.form.get("amount")
        reason = request.form.get("reason")
        if amount and amount.replace('.', '', 1).isdigit():
            new_cash_entry = Cash(amount=float(amount), reason=reason, user_id=current_user.id)
            db.session.add(new_cash_entry)
            db.session.commit()
            return redirect(url_for("add_cash"))

    # Retrieve all cash entries for the current user
    cash_entries = Cash.query.filter_by(user_id=current_user.id).all()
    return render_template('addcash.html', cash_entries=cash_entries, username=current_user.username)


@app.route("/dashboard")
@login_required
def dashboard():
    # Calculate total cash added by the user
    total_balance = db.session.query(func.sum(Cash.amount)).filter_by(user_id=current_user.id).scalar() or 0
    total_expenses = db.session.query(func.sum(Expenses.amount)).filter_by(user_id=current_user.id).scalar() or 0
    remaining_balance = total_balance - total_expenses

    # Group expenses by category and calculate the total amount per category
    expenses_summary = db.session.query(
        Expenses.category,
        func.sum(Expenses.amount).label('total_amount')
    ).filter_by(user_id=current_user.id).group_by(Expenses.category).all()
    
    return render_template("dashboard.html", 
                           total_balance=remaining_balance, 
                           expenses_summary=expenses_summary,
                           username=current_user.username)

@app.route("/addexpense", methods=["POST"])
@login_required
def add_expense():
    if request.method == "POST":
        category = request.form.get("category")
        amount = request.form.get("amount")
        
        # Check if amount is valid
        if not amount or not amount.replace('.', '', 1).isdigit():
            flash("Please enter a valid amount.")
            return redirect(url_for("track_expenses"))
        
        amount = float(amount)
        
        # Calculate remaining balance
        total_balance = db.session.query(func.sum(Cash.amount)).filter_by(user_id=current_user.id).scalar() or 0
        total_expenses = db.session.query(func.sum(Expenses.amount)).filter_by(user_id=current_user.id).scalar() or 0
        remaining_balance = total_balance - total_expenses
        
        # Check if adding this expense will exceed available balance
        if amount > remaining_balance:
            flash("Insufficient balance. Please enter a smaller amount.")
            return redirect(url_for("track_expenses"),username=current_user.username)
        
        # If balance is sufficient, proceed with adding the expense
        new_expense = Expenses(category=category, amount=amount, user_id=current_user.id)
        db.session.add(new_expense)
        db.session.commit()
        return redirect(url_for("track_expenses"))


@app.route('/trackexpenses', methods=['GET'])
@login_required
def track_expenses():
    expenses = Expenses.query.filter_by(user_id=current_user.id).all()
    return render_template('trackexpenses.html', expenses=expenses,username=current_user.username)  # Ensure 'trackexpenses.html' is the correct template name
@app.route("/logout")
@login_required
def logout():
    print("Logging out...")
    logout_user()
    return redirect(url_for("login"))




if __name__ == "__main__":
    app.run(port=8002)
