import os
import datetime

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Get symbol and sum of your shares history
    data = db.execute("SELECT symbol, sum(shares) AS shares FROM history WHERE user_id = ? GROUP BY symbol", session["user_id"])

    # Store the grand total
    infoUser = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
    total = float(infoUser[0]["cash"])

    # Add actual price, name and total for each share
    for share in data:
        # Get data of the symbol
        response = lookup(share["symbol"])

        # Add name, price and subtotal
        share["name"] = response["name"]
        share["price"] = response["price"]
        share["subtotal"] = response["price"] * int(share["shares"])

        # Add the subtotal to the total
        total += float(share["subtotal"])

    return render_template("portfolio.html", data=data, total=total, cash=float(infoUser[0]["cash"]))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == 'POST':

        # Get
        symbol = request.form.get('symbol')
        # Ensure valid symbol and shares
        if not symbol:
            return apology("MISSING SYMBOL", 400)

        try:
            shares = int(request.form.get('shares'))
        except:
            return apology("INVALID SHARES", 400)

        if not shares:
            return apology("MISSING SHARES", 400)
        if shares == 0:
            return apology("TOO FEW SHARES", 400)
        if shares < 0:
            return apology("INVALID SHARES", 400)

        # Get data of the requested symbol
        response = lookup(symbol.upper())

        # Ensure there is a valid answer
        if not response:
            return apology("INVALID SYMBOL", 400)

        # Query database for id
        rows = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])

        # Calculate amount to pay
        amount = response["price"] * shares

        # Ensure there is enough money
        if amount > rows[0]["cash"]:
            return apology("CAN'T AFFORD", 400)

        # Get current date an time
        currTime = datetime.datetime.now()
        # Format date and time
        currTime = str(currTime)
        currTime = currTime.split('.')[0]

        # Make cash discount
        db.execute("UPDATE users SET cash = ? WHERE id = ?", rows[0]["cash"] - amount, session["user_id"])

        # Query para almacenar en el historial la compra
        db.execute("INSERT INTO history (user_id, symbol, shares, price, date) VALUES(?, ?, ?, ?, ?)",
                   session["user_id"], response["symbol"], shares, response["price"], currTime)

        return redirect("/")

    else:
        return render_template('buy.html')


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    data = db.execute("SELECT * FROM history WHERE user_id = ?", session["user_id"])

    return render_template("history.html", data=data)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == 'POST':
        # Get symbol
        symbol = request.form.get("symbol")

        # Ensure symbol has been entered
        if not symbol:
            return apology("MISSING SYMBOL", 400)

        # Get data of the requested symbol
        response = lookup(symbol.upper())

        # Ensure there is a valid answer
        if not response:
            return apology("INVALID SYMBOL", 400)

        return render_template("quoted.html", response=response)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == 'POST':

        # Forget any user_id
        session.clear()

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username has been entered
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password has been entered
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure the user doesn't exist
        elif len(rows) != 0:
            return apology("User already exists", 400)

        # Ensure passwords are the same
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Passwords do not match", 400)

        # Query for user registration
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", request.form.get(
            "username"), generate_password_hash(request.form.get("password")))

        # Get id of new user
        newUser = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Automatic login
        session["user_id"] = newUser[0]["id"]

        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        # Get
        symbol = request.form.get('symbol')

        # Asegurar que haya un simbolo
        if not symbol:
            return apology("MISSING SYMBOL", 400)

        try:
            shares = int(request.form.get('shares'))
        except:
            return apology("INVALID SHARES", 400)

        # Asegurar que haya un share valido
        if shares == 0:
            return apology("TOO FEW SHARES", 400)
        if not shares:
            return apology("MISSING SHARES", 400)
        elif shares < 0:
            return apology("SHARES MUST BE POSITIVE", 400)

        data = db.execute("SELECT symbol, sum(shares) AS shares FROM history WHERE user_id = ? GROUP BY symbol", session["user_id"])

        # Verificar si el usuario tiene acciones del simbolo ingresado
        symbolValid, sharesValid = False, False
        for row in data:
            if row["symbol"] == symbol:
                symbolValid = True
                if shares <= row["shares"]:
                    sharesValid = True

        if not symbolValid:
            return apology("SYMBOL NOT OWNED", 400)
        if not sharesValid:
            return apology("TOO MANY SHARES", 400)

        # Query database for id
        userData = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])

        # Get data of the requested symbol
        response = lookup(symbol.upper())

        # Make cash increment
        db.execute("UPDATE users SET cash = ? WHERE id = ?", userData[0]["cash"] + shares * response["price"], session["user_id"])

        # Get current date an time
        currTime = datetime.datetime.now()
        # Format date and time
        currTime = str(currTime)
        currTime = currTime.split('.')[0]

        # Query para almacenar en el historial la compra
        db.execute("INSERT INTO history (user_id, symbol, shares, price, date) VALUES(?, ?, ?, ?, ?)",
                   session["user_id"], response["symbol"], shares * (-1), response["price"], currTime)

        return redirect("/")

    else:
        data = db.execute("SELECT symbol, sum(shares) AS shares FROM history WHERE user_id = ? GROUP BY symbol", session["user_id"])
        return render_template("sell.html", data=data)
