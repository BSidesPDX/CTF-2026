import base64
import json
import os
import re
import sqlite3
import time
from typing import Annotated
import uuid

from fastapi import Cookie, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


class Cookies(BaseModel):
    model_config = {"extra": "forbid"}
    Session: str


app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=re.compile(r'[a-z]{31}'),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def default_headers(request: Request, call_next):
    with sqlite3.connect("data/app.db") as db:
        cursor = db.cursor()
        session = request.cookies.get("Session")
        if session is None:
            session = {"key": str(uuid.uuid4()), "flag_access": False}
            cursor.execute("INSERT INTO sessions VALUES (?, ?)", (session["key"], time.time_ns()))
            db.commit()

        response = await call_next(request)

        response.headers["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; script-src nothing.invalid; connect-src 'none'"
        response.headers["server"] = "fastapi"
        session_cookie = base64.b64encode(bytes(json.dumps(session), encoding="utf-8")).decode("utf-8")
        response.set_cookie(key="Session", value=session_cookie, domain="null.void.invalid", secure=True, httponly=True)
        return response


@app.get("/")
def index():
    return Response("Hello world!", media_type="text/html")


@app.get("/_src")
def src():
    return "You'd like that, wouldn't you :)"


@app.get("/flag")
def flag(cookies: Annotated[Cookies, Cookie()], request: Request):
    with sqlite3.connect("data/app.db") as db:
        cursor = db.cursor()
        session_cookie = cookies.Session

        if session_cookie is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

        try:
            session_cookie_data = json.loads(str(base64.b64decode(session_cookie), encoding="utf-8"))
        except:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bad request")

        if "key" not in session_cookie_data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bad request")

        t = time.time_ns()
        res = cursor.execute("SELECT key, timestamp FROM sessions WHERE key=?", (session_cookie_data.get("key"),))
        session_t = res.fetchone()

        if session_t is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

        print(session_t, t)

        if t - session_t[1] > 1000000000:
            cursor.execute("DELETE FROM sessions WHERE key=?", (session_t[0],))
            db.commit()
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session expired")

        if not session_cookie_data.get("flag_access", False):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized. This event has been reported.")

        with open("flag.txt") as f:
            flag = f.read()

        return flag

