import sqlite3

with sqlite3.connect("data/app.db") as db:
    cursor = db.cursor()
    cursor.execute("CREATE TABLE sessions(key VARCHAR PRIMARY KEY, timestamp INTEGER)")
