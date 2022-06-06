import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

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
# db = SQL("sqlite:///finance.db")

uri = os.getenv("DATABASE_URL")
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://")
db = SQL(uri)

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

    # Current user
    user_id = session["user_id"]

    # Info for stocks the user owns
    stock_info = db.execute(
        "SELECT symbol, name, sum(shares) as shares_owned FROM transactions WHERE user_id = (?) GROUP BY symbol, name", user_id)

    current_cash = db.execute("SELECT cash FROM users WHERE id = (?)", user_id)[
        0]["cash"]

    shares = db.execute(
        "SELECT sum(shares) as shares_owned FROM transactions WHERE user_id = (?)", user_id)

    shares_val = db.execute(
        "SELECT sum(price * shares) as shares_val FROM transactions WHERE user_id=(?) AND shares > 0", user_id)

    total = current_cash
    profit_loss = 0
    for stock in stock_info:
        total += lookup(stock["symbol"])["price"] * stock["shares_owned"]

    return render_template("index.html", stock_info=stock_info, current_cash=usd(current_cash), total=usd(total), usd=usd, lookup=lookup, shares=shares, shares_val=shares_val)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # Display form to buy a stock
    if request.method == "GET":
        return render_template("buy.html")

    """ Method == "POST" """
    # Lookup the stock symbol
    quote_info = lookup(request.form.get("symbol"))

    # Number of shares entered by user
    try:
        shares = int(request.form.get("shares"))
    except:
        return apology("invalid amount")

    # Number of shares validation
    if shares <= 0:
        return apology("invalid amount")

    # Stock symbol validation
    if quote_info == None:
        return apology("invalid symbol")

    # Stock info
    stock = quote_info["name"]
    price = quote_info["price"]
    symb = quote_info["symbol"]

    # Cost of purchase
    cost = price * shares

    # Current user
    user_id = session["user_id"]

    # Query database for users current cash limit
    current_cash = db.execute("SELECT cash FROM users WHERE id = (?)", user_id)[
        0]["cash"]

    # Calculate cash remaining after purchase
    cash_remaining = current_cash - cost

    # Not enough cash
    if cash_remaining < 0:
        return apology("not enough cash")

    # Enough cash for the purchase
    else:
        # Update the users cash amount after the purchase
        db.execute("UPDATE users SET cash = (?) WHERE id = (?)",
                   cash_remaining, user_id)
        # Save purchase info in the database
        now = datetime.now()
        db.execute(
            "INSERT INTO transactions(user_id, type, name, symbol, shares, price, date_time) VALUES(?,?,?,?,?,?,?)", user_id, "BUY", stock, symb, shares, price, now)
        return render_template("bought.html", symbol=symb, name=stock, shares=shares, price=usd(price), purchase_total=usd(cost), cash_remaining=usd(cash_remaining))


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    user_id = session["user_id"]

    transaction_info = db.execute(
        "SELECT * FROM transactions WHERE user_id = (?)", user_id)

    return render_template("history.html", transaction_info=transaction_info)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        username = request.form.get("username")
        pw = request.form.get("password")

        # Ensure username was submitted
        if not username:
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not pw:
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = (?)", username)
        print(f"len(rows): {len(rows)}")

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], pw):
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
    """Get stock quote."""

    # Dispaly form to request a stock quote
    if request.method == "GET":
        return render_template("quote.html")

    # Lookup the stock symbol and display the results
    if request.method == "POST":

        # Lookup the stock symbol
        quote_info = lookup(request.form.get("symbol"))

        # If symbol exists display the results
        if quote_info != None:
            stock = quote_info["name"]
            price = quote_info["price"]
            symb = quote_info["symbol"]
            return render_template("quoted.html", name=stock, price=price, symbol=symb, usd=usd)

        # Symbol does not exist apology
        else:
            return apology("That stock symbol does not exist")


@ app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    if request.method == "GET":
        return render_template("register.html")

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        username = request.form.get("username")
        pw = request.form.get("password")
        pw_confirm = request.form.get("confirmation")

        # Ensure username was submitted
        if not username:
            return apology("must provide username")

        # Ensure password was submitted
        elif not pw:
            return apology("must provide password")

        # Ensure passwords match
        elif not pw == pw_confirm:
            return apology("passwords do not match")

        # Generate a hash of the password
        pw_hash = generate_password_hash(pw)

        # Insert new user and password hash into the database
        try:
            db.execute(
                "INSERT INTO users (username, hash) values (?, ?)", username, pw_hash)
        # Unless username already exists
        except:
            return apology("username already taken")

        # Remember which user has logged in
        rows = db.execute("SELECT * FROM users WHERE username = (?)", username)
        session["user_id"] = rows[0]["id"]

        # Redirect new user to index page
        return redirect("/")


@ app.route("/sell", methods=["GET", "POST"])
@ login_required
def sell():
    """Sell shares of stock"""

    # Current user
    user_id = session["user_id"]

    # Info for stocks the user owns
    stock_info = db.execute(
        "SELECT symbol, name, sum(shares) as shares_owned FROM transactions WHERE user_id = ? GROUP BY symbol, name", user_id)

    if request.method == "GET":
        return render_template("sell.html", stock_info=stock_info)

    if request.method == "POST":
        quote_info = lookup(request.form.get("symbol"))

        # Number of shares entered by user
        shares = int(request.form.get("shares"))

        # Number of shares validation
        if shares <= 0:
            return apology("invalid amount")

        # Stock symbol validation
        if quote_info == None:
            return apology("invalid symbol")

        # Stock info
        stock = quote_info["name"]
        price = quote_info["price"]
        symb = quote_info["symbol"]

        shares_owned = db.execute(
            "SELECT SUM(shares) as shares from TRANSACTIONS WHERE user_id = (?) and symbol = (?)", user_id, symb)

        # if shares > shares_owned return apology "too many shares"
        if shares > shares_owned[0]["shares"]:
            return apology("too many shares")
        else:
            now = datetime.now()

            # convert shares to negative
            shares = -abs(shares)

            sell_total = abs(shares * price)

            # Query database for users current cash limit
            current_cash = db.execute("SELECT cash FROM users WHERE id = (?)", user_id)[
                0]["cash"]

            # Calculate cash remaining after purchase
            cash_remaining = current_cash + sell_total

            db.execute(
                "INSERT INTO transactions(user_id, type, name, symbol, shares, price, date_time) VALUES(?,?,?,?,?,?,?)", user_id, "SELL", stock, symb, shares, price, now)

            # Add the sell_total to users cash
            updated_total = current_cash + sell_total
            db.execute(
                "UPDATE users SET cash = (?) WHERE id = (?)", updated_total, user_id)

            return render_template("sold.html", symbol=symb, name=stock, shares=shares, price=usd(price), sell_total=usd(sell_total), cash_remaining=usd(cash_remaining))


@ app.route("/add_cash", methods=["GET", "POST"])
@ login_required
def add_cash():

    # Current user
    user_id = session["user_id"]

    # Dispaly form to request a stock quote
    if request.method == "GET":
        return render_template("add_cash.html")

    # If method is POST
    if request.method == "POST":
        add_cash = request.form.get("add_cash")
        db.execute("UPDATE users SET cash = cash + (?) WHERE id = (?)",
                   add_cash, user_id)

        return redirect("/")
