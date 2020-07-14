import os

from cs50 import SQL
from flask import Flask, flash, redirect, url_for, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

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


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # get the cash remaining with the user
    cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id = session["user_id"])

    #get all the stocks bought by the user
    stocks = db.execute("SELECT symbol, SUM(shares) AS shares FROM portfolios WHERE user_id = :user_id GROUP BY symbol HAVING shares > 0",user_id = session["user_id"])
    quote = {}

    cash_remaining = cash[0]["cash"]

    for stock in stocks:
        quote[stock["symbol"]] = lookup(stock["symbol"])

    return render_template("portfolio.html",stocks = stocks, quote = quote,cash_remaining = cash_remaining)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == 'GET':
        return render_template("buy.html")
    else:
        quote = lookup(request.form.get("symbol"))

        # check for Invalid symbol
        if not quote:
            return apology("Invalid Symbol")

        #get the share count
        try:
           shares = int(request.form.get("shares"))
        except:
            return apology("shares must be a positive integer")

        # share count should be greater than zero
        if shares <= 0:
            return apology("shares must be a positive integer")

        # get the cash remaining with the user
        row = db.execute("SELECT cash FROM users WHERE id = :user_id",user_id = session["user_id"])

        # total $$$'s to be spent
        cash_remaining = row[0]["cash"]
        price_per_share = quote["price"]

        # Calculate the price of requested shares
        total_price = price_per_share * shares

        if total_price > cash_remaining:
            return apology("not enough funds")

        # update the cash field in uers table
        db.execute("UPDATE users SET cash = cash - :total_price WHERE id = :user_id",total_price = total_price, user_id = session["user_id"])
        try:
            db.execute("INSERT INTO portfolios (user_id,symbol,shares,price_per_share) VALUES (:user_id,:symbol,:shares,:price_per_share) ",
                user_id = session["user_id"],
                symbol = quote["symbol"],
                shares = shares,
                price_per_share = quote["price"])

        except RuntimeError:
            return apology("Error occured while INSERT operation")

        flash("bought!")
        return redirect(url_for("index"))

    return apology("TODO")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    return apology("TODO")


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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

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
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")
    else:

        quote = lookup(request.form.get("symbol"))
        print(quote)

        if not quote:
            return apology("Invalid Symbol")
        else:
            return render_template("quote-render.html",quote=quote)




@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    else:

        username = request.form.get("username")
        password = request.form.get("password")

        #make sure username is entered
        if not username:
            return apology("username not entered",400)
        elif not password:
            return apology("password not entered",400)
        elif password != request.form.get("confirmation"):
            return apology("confirmation do not match!")

        # hash the password and insert the user
        hash = generate_password_hash(password)
        user_id = db.execute("INSERT INTO users (username,hash) VALUES (:username,:hash)",username=username,hash=hash)  #ERROR OCCURING IN THIS LINE

        # check for duplicate username
        if not user_id:
            return apology("username already taken!")

        #store the session id of the logged in user
        session["user_id"] = user_id

        # flash the register message
        flash("registered!")

        #redirect user to the home page
        return redirect(url_for("index"))

    return apology("TODO")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        return render_template("sell.html")
    else:
        symbol = request.form.get("symbol")
        quote = lookup(symbol)

        if not quote:
            return apology("Invalid Symbol")

        shares  = int(request.form.get("shares"))



        if shares <= 0:
            return apology("Enter positive # of shares")

        # check for the shares available
        share_count = db.execute("SELECT SUM(shares) AS share FROM portfolios WHERE user_id = :user_id", user_id = session["user_id"])

        if share_count[0]["shares"] < shares:
            return apology("not enough shares to be sold")

        cash  = db.execute("SELECT cash FROM users WHERE id = :user_id",id = session["user_id"])

        total_share_price = shares * quote["price"];

        db.execute("UPDATE users SET cash -= :total_share_price", total_share_price = total_share_price)
        db.execute("UPDATE portfolios SET shares -= :shares ", shares = shares)

        flash("Sold!")
        redirect(url_for("index"))


    return apology("TODO")


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)


if __name__ == "__main__":
    app.run(debug=True)
