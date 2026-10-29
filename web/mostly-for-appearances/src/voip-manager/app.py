import os
import sys

import requests
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from peewee import CharField, Model, SqliteDatabase
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

DB_PATH = os.environ.get("DB_PATH", os.path.join("data", "app.db"))
database = SqliteDatabase(DB_PATH)


class User(Model, UserMixin):
    username = CharField(unique=True)
    password_hash = CharField()

    class Meta:
        database = database

    def verify_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


def init_db() -> None:
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    database.connect(reuse_if_open=True)
    database.create_tables([User], safe=True)


def create_user(username: str, password: str) -> User:
    user, created = User.get_or_create(
        username=username,
        defaults={
            "password_hash": generate_password_hash(password),
        },
    )
    return user


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", os.urandom(32).hex())
    # two proxies, kube ingress controller and apache
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=2, x_proto=2, x_host=2, x_prefix=2)

    login_manager = LoginManager()
    login_manager.login_view = "login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        return User.get_or_none(User.id == int(user_id))

    @app.before_request
    def _ensure_db_ready() -> None:
        if database.is_closed():
            init_db()

    @app.teardown_request
    def _close_db(_exc) -> None:
        if not database.is_closed():
            database.close()

    @app.route("/")
    @login_required
    def index():
        return render_template("index.html")

    @app.route("/phones")
    @login_required
    def get_phones():
        try:
            phone_manager_host = os.environ.get(
                "PHONE_MANAGER_HOST", "docker-orchestrator:8000"
            )
            base_url = f"http://{phone_manager_host}"

            if "extension" not in session:
                r = requests.get(f"{base_url}/available")
                if r.status_code == 507:
                    return jsonify(
                        {
                            "error": "VOIP instance manager out of extensions, please notify CTF admins"
                        }
                    ), 507

                session["extension"] = r.json()["ext"]

            phones = [
                {
                    "mac": "00:0C:CC:68:E0:CD",
                    "name": "Alice",
                    "model": "CP-7912G-A",
                    "private_ip": "10.0.50.22",
                    "status": "Online",
                    "extension": session["extension"],
                    "remote_url": "/remote",
                },
                {
                    "mac": "00:0C:CC:DD:BF:F2",
                    "name": "Theresa",
                    "model": "CP-7912G-A",
                    "private_ip": "10.0.50.140",
                    "extension": "",
                    "status": "Offline",
                },
                {
                    "mac": "00:0C:CC:B6:F8:9A",
                    "name": "Dylan",
                    "model": "CP-7912G-A",
                    "private_ip": "10.0.50.85",
                    "extension": "",
                    "status": "Offline",
                },
            ]
            return jsonify(phones)
        except Exception as e:
            print(f"Error in get_phones: {e}", file=sys.stderr)
            return jsonify(
                {"error": "Unintended VOIP chal error, please notify CTF admins"}
            ), 500

    @app.route("/remote")
    @login_required
    def remote_redirect():
        phone_manager_host = os.environ.get(
            "PHONE_MANAGER_HOST", "docker-orchestrator:8000"
        )
        base_url = f"http://{phone_manager_host}"

        if "extension" not in session:
            return redirect(url_for("index"))

        try:
            r = requests.post(f"{base_url}/new", params={"ext": session["extension"]})
            if r.status_code == 409:
                print(
                    f"Warning: VOIP instance manager already has an instance for extension {session['extension']}"
                )
                r = requests.get(
                    f"{base_url}/info", params={"ext": session["extension"]}
                )
                print(f"got info instead: {r.status_code} {r.json()}")

            if r.ok and "phone_ui" in r.json():
                session["phone_url"] = r.json()["phone_ui"]
        except Exception as e:
            print(f"Error creating phone instance: {e}", file=sys.stderr)

        return render_template("redirect.html")

    @app.route("/remote/check")
    @login_required
    def remote_check():
        if "phone_url" not in session:
            return jsonify({"ready": False, "error": "No phone UI URL provided"})

        if "extension" not in session:
            return jsonify({"ready": False, "error": "No extension assigned"})

        try:
            r = requests.get(session["phone_url"], timeout=5, verify=False)
            if r.status_code == 200:
                return jsonify({"ready": True, "phone_url": session["phone_url"]})
        except Exception as e:
            print(f"Error checking phone status: {e}", file=sys.stderr)

        return jsonify({"ready": False})

    @app.route("/login", methods=["GET"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("index"))

        if request.args.get("username") or request.args.get("password"):
            username = request.args.get("username", "").strip()
            password = request.args.get("password", "")

            user = User.get_or_none(User.username == username)
            if not user or not user.verify_password(password):
                flash("Invalid username or password.", "error")
                return render_template("login.html")

            login_user(user)
            return redirect(url_for("index"))

        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        session.pop("extension", None)
        session.pop("phone_url", None)
        return redirect(url_for("login"))

    @app.route("/readyz")
    def ready():
        return "OK", 200

    return app
