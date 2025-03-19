from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session, send_from_directory
from flask_bcrypt import Bcrypt
from flask_mail import Mail, Message
from pymongo import MongoClient
import random
from dotenv import load_dotenv
import os 
from datetime import datetime, timedelta
from bson import ObjectId


load_dotenv()
app = Flask(__name__)
app.secret_key = "This_is_Expense_Tracker"


client = MongoClient(os.getenv('MONGODB_URL'))
db = client['expense_tracker']
users_collection = db['users']

bcrypt = Bcrypt(app)


app.config["MAIL_SERVER"] = "smtp-relay.brevo.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = "8114b8001@smtp-brevo.com"
app.config["MAIL_PASSWORD"] = os.getenv('SMTP_PASSWORD')
mail = Mail(app)


@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route("/", methods=["GET", "POST"])
def home():
    if "user" not in session:
        return redirect(url_for("login"))
    
    
    user_email = session["user"]
    user = users_collection.find_one({"email": user_email})
    first_name = user["first_name"]  
    
    return render_template("index.html", first_name=first_name)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        
        
        user = users_collection.find_one({"email": email})

        if not user:
            flash("Invalid user email. Please register first.", "error")
            return render_template("login.html")

       
        if not bcrypt.check_password_hash(user["password"], password):
            flash("Please enter a correct password.", "error")
            return render_template("login.html")

        
        session["user"] = email
        # flash("Login successful!", "success")
        return redirect(url_for("home"))

    return render_template("login.html")

@app.route("/signin", methods=["GET", "POST"])
def signin():
    if request.method == "POST":
        first_name = request.form.get("first_name").strip()
        last_name = request.form.get("last_name").strip()
        email = request.form.get("email").strip()
        password = request.form.get("password")
        age = request.form.get("age").strip()
        phone = request.form.get("phone").strip()

        
        if users_collection.find_one({"email": email}):
            flash("Email already exists. Please log in.", "error")
        else:
            hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
            users_collection.insert_one({
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "password": hashed_password,
                "age": age,
                "phone": phone
            })
            flash("Account created successfully. Please log in.", "success")
            return redirect(url_for("login"))

    return render_template("signin.html")

@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        email = request.form["email"]
        user = users_collection.find_one({"email": email})
        if user:
            otp = random.randint(100000, 999999)
            session["otp"] = otp
            session["reset_email"] = email
            msg = Message("Password Reset OTP", sender="kushikumarbkushikumarb@gmail.com", recipients=[email])
            msg.body = f"Your OTP is {otp}."
            mail.send(msg)
            return redirect(url_for("reset_password"))
        flash("Email not found.", "error")
    return render_template("forgot.html")

@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        otp = int(request.form["otp"])
        if otp == session.get("otp"):
            new_password = bcrypt.generate_password_hash(request.form["new_password"]).decode("utf-8")
            email = session.get("reset_email")
            users_collection.update_one({"email": email}, {"$set": {"password": new_password}})
            flash("Password updated successfully. Please log in.", "success")
            return redirect(url_for("login"))
        else:
            flash("Invalid OTP.", "error")
    return render_template("reset_password.html")

@app.route("/add_expense", methods=["POST"])
def add_expense():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    required_fields = ["name", "amount", "category", "date"]

    
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Invalid data"}), 400

    try:
        date_obj = datetime.strptime(data["date"], "%Y-%m-%d")
        expense = {
            "user_email": session["user"],
            "name": data["name"],
            "amount": float(data["amount"]),
            "category": data["category"],
            "date": date_obj
        }
        db["expenses"].insert_one(expense)
        return jsonify({"message": "Expense added successfully"}), 201

    except Exception as e:
        print(f"Error inserting expense: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/expenses", methods=["GET"])
def get_expenses():
    if "user" not in session:
        return redirect(url_for("login"))

    user_email = session["user"]
    expenses = list(db["expenses"].find({"user_email": user_email}))
    for expense in expenses:
        expense["_id"] = str(expense["_id"])  
        expense["date"] = expense["date"].strftime("%Y-%m-%d")  
    return render_template("expense.html", expenses=expenses)

@app.route("/delete_expense", methods=["POST"])
def delete_expense():
    if "user" not in session:
        return redirect(url_for("login"))

    expense_id = request.form['id']
    db["expenses"].delete_one({"_id": ObjectId(expense_id)})
    return redirect(url_for("get_expenses"))

@app.route("/edit_expense/<expense_id>", methods=["GET", "POST"])
def edit_expense(expense_id):
    if "user" not in session:
        return redirect(url_for("login"))

    expense = db["expenses"].find_one({"_id": ObjectId(expense_id), "user_email": session["user"]})
    if not expense:
        flash("Expense not found or you do not have permission to edit this expense.", "error")
        return redirect(url_for("get_expenses"))

    if request.method == "POST":
        try:
            updated_data = {
                "name": request.form["name"].strip(),
                "amount": float(request.form["amount"]),
                "category": request.form["category"].strip(),
                "date": datetime.strptime(request.form["date"], "%Y-%m-%d")  
            }
            db["expenses"].update_one(
                {"_id": ObjectId(expense_id), "user_email": session["user"]},
                {"$set": updated_data}
            )
            flash("Expense updated successfully!", "success")
            return redirect(url_for("get_expenses"))
        except ValueError:
            flash("Invalid input. Please ensure all fields are correctly filled.", "error")
        except Exception as e:
            flash(f"An error occurred while updating the expense: {str(e)}", "error")
    return render_template("edit_expense.html", expense=expense)

@app.route("/daily_expenses", methods=["GET"])
def daily_expenses():
    try:
        date_str = request.args.get("date", datetime.today().strftime("%Y-%m-%d"))
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        selected_date_as_datetime = datetime.combine(selected_date, datetime.min.time())

        daily_expenses = list(db["expenses"].find({"date": selected_date_as_datetime, "user_email": session["user"]}))

        if not daily_expenses:
            return render_template("daily_expenses.html", labels=[], values=[], date=date_str)

        category_totals = {}
        for expense in daily_expenses:
            category = expense["category"]
            amount = expense["amount"]
            category_totals[category] = category_totals.get(category, 0) + amount

        labels = list(category_totals.keys())
        values = list(category_totals.values())

        return render_template("daily_expenses.html", labels=labels, values=values, date=date_str)
    except Exception as e:
        return str(e), 500

@app.route("/weekly_expenses/<int:week_offset>", methods=["GET"])
def weekly_expenses(week_offset=0):
    try:
        today = datetime.today()
        start_of_week = today - timedelta(days=today.weekday() + 1 + (week_offset * 7))  
        end_of_week = start_of_week + timedelta(days=6)  

        expenses = db["expenses"].find({
            "date": {
                "$gte": start_of_week,
                "$lte": end_of_week
            },
            "user_email": session["user"]
        })

        
        weekly_data = {}
        for i in range(7):
            day = start_of_week + timedelta(days=i)
            day_name = day.strftime("%A")
            date_str = day.strftime("%Y-%m-%d")
            weekly_data[date_str] = {"day": day_name, "date": date_str, "expense": 0}

       
        for expense in expenses:
            expense_date = expense["date"].strftime("%Y-%m-%d")
            if expense_date in weekly_data:
                weekly_data[expense_date]["expense"] += expense["amount"]

        
        return jsonify(list(weekly_data.values()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/weekly")
def weekly_page():
    return render_template("weekly.html")

@app.route("/monthly_expenses", methods=["GET"])
def monthly_expenses():
    try:
        year = int(request.args.get("year", datetime.today().year))

       
        expenses = list(db["expenses"].find({"date": {"$gte": datetime(year, 1, 1), "$lt": datetime(year + 1, 1, 1)}, "user_email": session["user"]}))

    
        monthly_totals = {month: 0 for month in range(1, 13)}
        for expense in expenses:
            month = expense["date"].month
            monthly_totals[month] += expense["amount"]

        
        labels = [datetime(year, month, 1).strftime("%B") for month in range(1, 13)]
        values = [monthly_totals[month] for month in range(1, 13)]

        return render_template("monthly.html", labels=labels, values=values, year=year)
    except Exception as e:
        return str(e), 500

@app.route("/yearly_expenses", methods=["GET"])
def yearly_expenses():
    try:
        base_year = int(request.args.get("year", datetime.today().year))

        start_year = base_year - 2
        end_year = base_year + 2
        expenses = list(
            db["expenses"].find(
                {
                    "date": {
                        "$gte": datetime(start_year, 1, 1),
                        "$lt": datetime(end_year + 1, 1, 1),
                    },
                    "user_email": session["user"]
                }
            )
        )

        
        yearly_totals = {year: 0 for year in range(start_year, end_year + 1)}
        for expense in expenses:
            year = expense["date"].year
            yearly_totals[year] += expense["amount"]

       
        labels = list(yearly_totals.keys())
        values = list(yearly_totals.values())

        return render_template("yearly.html", labels=labels, values=values, base_year=base_year)
    except Exception as e:
        return str(e), 500

@app.route("/contact-us")
def contact_us():
    return render_template("contact-us.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user", None)  
    return redirect(url_for("login")) 


if __name__ == "__main__":
    app.run(debug=True)
