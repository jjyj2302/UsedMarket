# app/models/product.py

def get_all_products(db):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM product")
    return cursor.fetchall()

def get_product_by_id(db, product_id):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM product WHERE id = ?", (product_id,))
    return cursor.fetchone()

def create_product(db, product_id, title, description, price, seller_id):
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO product (id, title, description, price, seller_id) VALUES (?, ?, ?, ?, ?)",
        (product_id, title, description, price, seller_id)
    )
    db.commit()

def delete_product_by_id(db, product_id):
    cursor = db.cursor()
    cursor.execute("DELETE FROM product WHERE id = ?", (product_id,))
    db.commit()

def delete_products_by_seller(db, seller_id):
    cursor = db.cursor()
    cursor.execute("DELETE FROM product WHERE seller_id = ?", (seller_id,))
    db.commit()
