import json
import urllib.request

from flask import redirect, render_template, request, session, url_for
from functools import wraps


def apology(top="", bottom=""):
    """Renders message as an apology to user."""

    def escape(s):
        """
        Escape special characters.
        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s

    return render_template("apology.html", top=escape(top), bottom=escape(bottom))


def login_required(f):
    """
    Decorate routes to require login.
    http://flask.pocoo.org/docs/0.11/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)

    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""
    # reject symbol if it starts with caret
    if symbol.startswith("^"):
        return None
    # reject symbol if it contains comma
    if "," in symbol:
        return None

    try:

        url = f"https://api.iextrading.com/1.0/stock/{symbol}/quote?filter=symbol,companyName,latestPrice"

        webpage = urllib.request.urlopen(url)

        data = webpage.read()

        stock_data = json.loads(data)

        # ensure stock exists
        try:
            price = float(stock_data['latestPrice'])
        except:
            return None

        return {
            "name": stock_data['companyName'],
            "price": price,
            "symbol": stock_data['symbol'].upper()
        }

    except:
        return None


def usd(value):
    """Formats value as USD."""
    return "${:,.3f}".format(value)
