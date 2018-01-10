from flask import Flask, flash, abort
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp
from sql import *
from helpers import *

# configure application
app = Flask(__name__)
# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response
# custom filter
app.jinja_env.filters["usd"] = usd
# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)
# configure Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    # get user available money
    rows = db.execute("""SELECT cash FROM users WHERE id=:id""", id=session['user_id'])
    if rows is None:
        abort(400)
    # get user cash
    cash = rows[0]['cash']
    total = cash
    stocks = db.execute(
        """SELECT symbol, SUM(shares) AS shares FROM transactions WHERE user_id=:id 
GROUP BY symbol HAVING SUM(shares) > 0""",
        id=session['user_id'])

    # retrieves and updates stock info
    for stock in stocks:
        quote = lookup(stock['symbol'])
        total += stock['shares'] * quote['price']
        stock.update({'name': quote['name'], 'price': quote['price']})

    return render_template('index.html', cash=cash, stocks=stocks, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    if request.method == "POST":
        # validate form
        if not request.form.get('symbol'):
            return apology('missing symbol')
        elif not re.match('^[1-9]\d*$', request.form.get('shares')):
            return apology('missing and/or invalid shares')
        # get stock info
        share = lookup(request.form.get('symbol'))
        if share is None:
            return apology('invalid symbol')
        shares = int(request.form.get('shares'))
        # total cost
        cost = shares * share['price']
        # get user available money
        rows = db.execute("""SELECT * FROM users WHERE id=:id""", id=session['user_id'])
        if rows is None:
            abort(400)
        # validate if user can afford
        if cost > rows[0]['cash']:
            return apology('you don\'t have enough cash')

        # adds shares to the user's transactions
        db.execute("""INSERT INTO transactions (user_id, symbol, shares, price)
 VALUES(:user_id,:symbol,:shares, :price)""",
                   user_id=session['user_id'], symbol=share['symbol'], shares=shares, price=share['price'])
        # updates the user's cash
        db.execute("""UPDATE users SET cash = cash - :cost WHERE id=:id""",
                   cost=cost, id=session['user_id'])

        flash('Bought')
        # goes to the user's portfolio after buy operation
        return redirect(url_for('index'))
    else:
        return render_template('buy.html')


@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    transactions = db.execute(
        """SELECT * FROM transactions WHERE user_id=:user_id""", user_id=session['user_id'])
    return render_template('history.html', transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""
    # forget any user_id
    session.clear()
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # ensure username was submitted
        if not request.form.get("username"):
            return apology("missing username")
        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("missing password")
        # query database for username
        rows = db.execute("""SELECT * FROM users WHERE username = :username""",
                          username=request.form.get("username"))
        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")
        # remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session['username'] = request.form.get('username')
        # redirect user to home page
        return redirect(url_for("index"))
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out."""
    # forget any user_id
    session.clear()
    # redirect user to login form
    return redirect(url_for("login"))


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        if not request.form.get('symbol'):
            return apology("missing symbol")
        share = lookup(request.form.get('symbol'))
        if share is None:
            return apology("invalid symbol")
        return render_template('quote.html', share=share)
    else:
        return render_template('index.html')


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("missing username")
        elif not request.form.get("password"):
            return apology("missing password")
        elif not request.form.get("confirm"):
            return apology("confirm password")
        elif request.form.get('password') != request.form.get('confirm'):
            return apology("passwords don't match")

        _id = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",
                         username=request.form.get('username'), hash=pwd_context.hash(request.form.get('password')))

        if _id is None:
            return apology("username already exists")
        session['user_id'] = _id
        session['username'] = request.form.get('username')
        flash('Registered')
        return redirect(url_for('index'))
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    if request.method == "POST":
        # validate form
        if not request.form.get('symbol'):
            return apology('missing symbol')
        elif not re.match('^[1-9]\d*$', request.form.get('shares')):
            return apology('missing and/or invalid shares')
        # get uppercase symbol
        symbol = request.form.get('symbol').upper()
        # get number of shares as integer
        shares = int(request.form.get('shares'))
        rows = db.execute("""SELECT SUM(shares) AS shares FROM transactions 
WHERE user_id=:user_id AND symbol=:symbol GROUP BY symbol""",
                          user_id=session['user_id'], symbol=symbol)
        # print(rows)
        # validate database query and number of shares to sell
        if len(rows) != 1:
            return apology('share not found')
        elif shares > rows[0]['shares']:
            return apology('too many shares')
        # update total's user shares sold
        share = lookup(symbol)
        db.execute("""INSERT INTO transactions (user_id,symbol,shares,price) VALUES(:user_id,:symbol,:shares,:price)""",
                   user_id=session['user_id'], symbol=symbol, shares=-shares, price=share['price'])
        # update users cash
        db.execute("""UPDATE users SET cash = cash + :value WHERE id=:id""",
                   value=(shares * share['price']), id=session['user_id'])
        flash('Sold')
        return redirect(url_for('index'))
    else:
        return render_template('sell.html')


@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    """Change password user."""
    if request.method == "POST":
        user = db.execute("""SELECT * FROM users WHERE id=:user_id""",
                          user_id=session['user_id'])

        if not request.form.get("pw"):
            return apology("missing current password")
        elif not pwd_context.verify(request.form.get("pw"), user[0]["hash"]):
            return apology("password incorrect")
        elif not re.match("^(?=.*\d)(?=.*[A-z])[0-9A-z!@#$%]{4,25}$", request.form.get("new_pw")):
            return apology("minimum of 4 characters (letters and digits)")
        elif pwd_context.verify(request.form.get("new_pw"), user[0]["hash"]):
            return apology("password should be different from the last one")
        elif request.form.get("new_pw") != request.form.get("rep_new_pw"):
            return apology("passwords don't match")

        # update users cash
        db.execute("""UPDATE users SET hash=:hash WHERE id=:id""",
                   hash=pwd_context.hash(request.form.get('new_pw')), id=session['user_id'])

        flash('Changed password')
        return redirect(url_for('index'))
    else:
        return render_template("change_password.html")


@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    """Reset password user."""
    if request.method == "POST":
        # "TODO"
        return redirect(url_for('index'))
    else:
        return render_template("reset_password.html")
