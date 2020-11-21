import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    myString = f"SELECT symbol, SUM(shares) as shares FROM log WHERE user_id = {session['user_id']} GROUP BY symbol HAVING SUM(shares) > 0;"
    info = db.execute(myString)

    portfolio = 0

    for item in info:
        stock = lookup(item['symbol'])
        shares = item['shares']
        name = stock['name']
        price = stock['price']
        total = shares * price
        portfolio += total

        item['name'] = name
        item['price'] = price
        item['total'] = "{:.2f}".format(total)

    # query the cash amount
    cash = db.execute("SELECT cash FROM users WHERE id = {}".format(
        session["user_id"]))[0]['cash']

    # calc. the total portfolio value
    portfolio += cash

    return render_template("index.html", info=info, cash="{:.2f}".format(cash), portfolio="{:.2f}".format(portfolio))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":

        # Look up the price info of the stock
        quoteInfo = lookup(request.form.get("symbol"))

        # Parse the shares to purchase
        shares = request.form.get("shares")

        # Get the current cash amount from db
        cash = db.execute("SELECT cash FROM users WHERE id = {}".format(
            session["user_id"]))[0]['cash']

        # Checking:
        if quoteInfo is None:
            return apology("Invalid symbol")

        if int(shares) < 0:
            return apology("Shares must be positive.")

        if float(cash) < quoteInfo['price'] * int(shares):
            return apology("Not enough cash.")

        # After all checking passed:
        currentTimestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Update the log with a 'Buy' action

        user_id = session['user_id']
        username = db.execute(f"SELECT username FROM users WHERE id = {user_id}")[0]['username']
        symbol = quoteInfo['symbol']
        price = quoteInfo['price']
        action = 'Buy'
        timestamp = currentTimestamp

        myString = f"INSERT INTO log ('user_id', 'username', 'symbol', 'shares', 'price', 'action', 'timestamp') VALUES ({user_id}, '{username}', '{symbol}', {shares}, {price}, '{action}', '{timestamp}');"

        db.execute(myString)

        # Update the cash of the user
        cash = float(cash) - float(quoteInfo['price']) * float(shares)
        myString = f"UPDATE users SET cash = {cash} WHERE id = {user_id};"
        db.execute(myString)

        return redirect("/")

    # GET
    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    myString = "SELECT * FROM log WHERE user_id = {}".format(
        session["user_id"])
    history = db.execute(myString)

    return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?",
                          request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

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

    if request.method == "POST":
        """Get stock quote."""

        quoteInfo = lookup(request.form.get("symbol"))

        if quoteInfo is None:
            return apology("Invalid symbol")

        return render_template("quoted.html", quoteInfo=quoteInfo)

    # GET
    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        password_confirmation = request.form.get("password-confirmation")

        # Checking: username has already been registered
        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        if len(rows) == 1:
            return apology("The username has been registered.")

        # Checking: password confirmation
        if password != password_confirmation:
            return apology("The passwords are not the same.")

        # Save the login info into db
        password_hash = generate_password_hash(password)
        db.execute("INSERT INTO users ('username', 'hash') VALUES ('{}', '{}');".format(
            username, password_hash))

        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    
    # POST
    if request.method == "POST":
        stock_to_sell = request.form.get("symbol")
        shares_to_sell = int(request.form.get("shares"))

        # Checking
        myString = f"SELECT symbol, SUM(shares) as shares FROM log WHERE user_id = {session['user_id']} AND symbol = '{stock_to_sell}' GROUP BY symbol HAVING SUM(shares) > 0;"
        stocks = db.execute(myString)

        if len(stocks) == 0:
            return apology('Invalid symbol')

        if int(stocks[0]['shares']) < shares_to_sell:
            return apology("Not enough shares")


        # After all checking passed:
        currentTimestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Update the log with a 'Sell' action

        # Look up the price info of the stock
        quoteInfo = lookup(request.form.get("symbol"))

        # Get the current cash amount from db
        cash = db.execute("SELECT cash FROM users WHERE id = {}".format(
            session["user_id"]))[0]['cash']

        user_id = session['user_id']
        username = db.execute(f"SELECT username FROM users WHERE id = {user_id}")[0]['username']
        symbol = quoteInfo['symbol']
        price = quoteInfo['price']
        action = 'Sell'
        timestamp = currentTimestamp

        myString = f"INSERT INTO log ('user_id', 'username', 'symbol', 'shares', 'price', 'action', 'timestamp') VALUES ({user_id}, '{username}', '{symbol}', {-shares_to_sell}, {price}, '{action}', '{timestamp}');"

        db.execute(myString)

        # Update the cash of the user
        cash = float(cash) + float(quoteInfo['price']) * float(shares_to_sell)
        myString = f"UPDATE users SET cash = {cash} WHERE id = {user_id};"
        db.execute(myString)

        return redirect("/")
        

    # GET
    myString = f"SELECT symbol, SUM(shares) as shares FROM log WHERE user_id = {session['user_id']} GROUP BY symbol HAVING SUM(shares) > 0;"
    stocks = db.execute(myString)
    return render_template("sell.html", stocks=stocks)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
