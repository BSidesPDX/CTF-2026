#!/usr/bin/env python3

import logging
import os
from functools import wraps

from authlib.integrations.flask_client import OAuth
from flask import Flask, redirect, send_file, send_from_directory, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(32))
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

OAUTH_METADATA_URL = os.environ.get("OAUTH_METADATA_URL", None)
if OAUTH_METADATA_URL is None:
    raise Exception("envvar OAUTH_METADATA_URL is not set!")

oauth = OAuth(app)
oauth.register(
    name="tangerinesso",
    client_id=os.environ.get("OAUTH_CLIENT_ID", "flag-email"),
    client_secret=os.environ.get("OAUTH_CLIENT_SECRET", ""),
    server_metadata_url=OAUTH_METADATA_URL,
    client_kwargs={"scope": "openid profile email"},
)


@app.route("/login")
def login():
    redirect_uri = url_for("callback", _external=True, _scheme="https")
    return oauth.tangerinesso.authorize_redirect(redirect_uri)


@app.route("/callback")
def callback():
    token = oauth.tangerinesso.authorize_access_token()
    user = token.get("userinfo")
    if user:
        session["user"] = dict(user)
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated


@app.route("/")
@login_required
def index():
    return send_file("static/index.html")


@app.route("/images/<path:filename>")
@login_required
def images(filename):
    return send_from_directory("static/images", filename)


@app.route("/readyz")
def ready():
    return "OK\n"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
