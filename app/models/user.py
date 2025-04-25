# app/models/user.py

def get_user_by_id(db, user_id):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM user WHERE id = ?", (user_id,))
    return cursor.fetchone()

def get_user_by_username(db, username):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM user WHERE username = ?", (username,))
    return cursor.fetchone()

def create_user(db, user_id, username, hashed_password):
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO user (id, username, password) VALUES (?, ?, ?)",
        (user_id, username, hashed_password)
    )
    db.commit()
