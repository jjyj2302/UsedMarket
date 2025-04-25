# app/models/report.py

def create_report(db, report_id, reporter_id, target_id, reason):
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO report (id, reporter_id, target_id, reason) VALUES (?, ?, ?, ?)",
        (report_id, reporter_id, target_id, reason)
    )
    db.commit()

def get_all_reports(db):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM report")
    return cursor.fetchall()
