import os

from cs50 import SQL
from flask import Flask, flash, redirect, url_for, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash
#from flask_ngrok import run_with_ngrok

from datetime import datetime
import pytz

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)
#run_with_ngrok(app) #start ngrok when app is run

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    #response.headers["Expires"] = 0
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
    stocks = db.execute("SELECT symbol, shares FROM portfolios WHERE user_id = :user_id ",user_id = session["user_id"])
    quote = {}

    cash_remaining = cash[0]["cash"]

    for stock in stocks:
        quote[stock["symbol"]] = lookup(stock["symbol"])

    #print(quote)

    return render_template("portfolio.html",stocks = stocks, quote = quote,cash_remaining = cash_remaining)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == 'GET':
        return render_template("buy.html")
    else:
        quote = lookup(request.form.get("symbol"))
        symbol = (request.form.get("symbol")).upper()

        # check for Invalid symbol
        if not quote:
            return apology("Invalid Symbol")

        #get the share count

        shares = int(request.form.get("shares"))


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


        # check if the stock has been bought before or not and then either insert or update correponding shares
        exists = db.execute("SELECT * FROM portfolios WHERE user_id = :user_id AND symbol = :symbol",user_id = session["user_id"], symbol = symbol)
        if not exists:
            db.execute("INSERT INTO portfolios (user_id, symbol, shares, price_per_share) VALUES (:user_id,:symbol,:shares, :price_per_share)",
                user_id= session["user_id"],
                symbol = symbol ,
                shares = shares,
                price_per_share = price_per_share)
        else:
            db.execute("UPDATE portfolios SET shares = shares + :shares WHERE user_id = :user_id AND symbol = :symbol",shares = shares , user_id = session["user_id"],symbol = symbol )

        # update the cash field in uers table
        db.execute("UPDATE users SET cash = cash - :total_price WHERE id = :user_id",total_price = total_price, user_id = session["user_id"])

         # Insert transaction INFO into the transactions table AFTER the sell operation
        db.execute("INSERT INTO transactions (user_id, symbol, shares,  trans_type) VALUES (:user_id, :symbol, :shares, :trans_type )",
            user_id = session["user_id"],
            symbol = symbol,
            shares = shares,
            trans_type = 'BUY')


        flash("bought!")
        return redirect(url_for("index"))

    return apology("TODO")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute("SELECT symbol, shares, trans_type, datetime( trans_time,'localtime','+05:30') as transacted_at FROM transactions WHERE user_id = :user_id", user_id = session["user_id"])

    # display user's transactions
    return render_template("history.html",rows = rows)




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

@app.route("/change_password",methods=["GET","POST"])
def change_password():
    """ change password """

    if request.method == 'GET':
        return render_template("change-password.html")

    return apology("TODO")


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

@app.route("/add_funds", methods=["GET", "POST"])
@login_required
def add_funds():
    """ Add More funds , If Your Portfolio needs and Doing Well """
    if request.method == 'GET':
        flash("Balance Remaining: $5000 !")
        return render_template("Add-Funds.html")
    else:
        amount = int(request.form.get("amount"))

        if amount > 5000:
            return apology("Balance Not Available !")
        else:
            db.execute("UPDATE users SET cash = cash + :amount WHERE id = :user_id",amount = amount, user_id = session["user_id"])
            flash("Funds Added !")
            return redirect(url_for("index"))




@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        return render_template("sell.html")
    else:
        symbol = (request.form.get("symbol")).upper()
        quote = lookup(symbol)

        if not quote:
            return apology("Invalid Symbol")

        shares  = int(request.form.get("shares"))



        if shares <= 0:
            return apology("Enter positive # of shares")

        # check for the shares available
        share_count = db.execute("SELECT shares FROM portfolios WHERE user_id = :user_id AND symbol = :symbol", user_id = session["user_id"], symbol = symbol)

        if not share_count:
            return apology("You Haven't Bought this share Yet")

        if share_count[0]["shares"] < shares:
            return apology("not enough shares to be sold")

        cash  = db.execute("SELECT cash FROM users WHERE id = :user_id",user_id = session["user_id"])

        total_share_price = shares * quote["price"];

        db.execute("UPDATE users SET cash = cash + :total_share_price WHERE id = :user_id", total_share_price = total_share_price, user_id = session["user_id"])
        db.execute("UPDATE portfolios SET shares = shares - :shares WHERE user_id = :user_id AND symbol = :symbol", shares = shares, user_id = session["user_id"], symbol = symbol)





        # delete the row if share_count reaches 0
        row = db.execute("SELECT shares FROM portfolios WHERE user_id = :user_id AND symbol = :symbol", user_id = session["user_id"], symbol = symbol)

        if row[0]["shares"] <= 0:
            db.execute("DELETE FROM portfolios WHERE user_id = :user_id AND symbol = :symbol", user_id = session["user_id"], symbol = symbol)

         # Insert transaction INFO into the transactions table AFTER the sell operation
        db.execute("INSERT INTO transactions (user_id, symbol, shares,  trans_type) VALUES (:user_id, :symbol, :shares, :trans_type )",
            user_id = session["user_id"],
            symbol = symbol,
            shares = shares,
            trans_type = 'SELL')

         # Implemnt History thing here
        flash("Sold!")
        return redirect(url_for("index"))


    return apology("TODO")


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)


if __name__ == "__main__":
    app.run(debug=True)
