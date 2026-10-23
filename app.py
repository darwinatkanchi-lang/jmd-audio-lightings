import os
import sqlite3
import secrets
from pathlib import Path
from urllib.parse import quote
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "instance" / "jmd.sqlite3"
IMAGE_DIR = BASE_DIR / "static" / "images"
VIDEO_DIR = BASE_DIR / "static" / "videos"
ALLOWED_IMAGES = {"jpg", "jpeg", "png", "webp"}
ALLOWED_VIDEOS = {"mp4", "webm", "mov"}
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "100"))

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

BUSINESS_NAME = "JMD Audio and Lightings"
BUSINESS_ADDRESS = "Kanchipuram, Tamil Nadu"
INSTAGRAM_URL = "https://www.instagram.com/dj_darwin_kanchi/"
WHATSAPP_NUMBER = os.environ.get("WHATSAPP_NUMBER", "")  # Example India format: 91XXXXXXXXXX
BUSINESS_PHONE = os.environ.get("BUSINESS_PHONE", "")
BUSINESS_EMAIL = os.environ.get("BUSINESS_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ChangeThisAdminPassword123!")

def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
            review_text TEXT NOT NULL,
            approved INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

def admin_required():
    return session.get("is_admin") is True

@app.context_processor
def common_data():
    return {
        "business_name": BUSINESS_NAME,
        "business_address": BUSINESS_ADDRESS,
        "instagram_url": INSTAGRAM_URL,
        "whatsapp_number": WHATSAPP_NUMBER,
        "business_phone": BUSINESS_PHONE,
        "business_email": BUSINESS_EMAIL,
        "admin_logged_in": admin_required()
    }
@app.route("/google997b3a6b1056a0ca.html")
def google_verification():
    file_path = BASE_DIR / "Google997b3a6b1056a0ca.html"
    return app.response_class(
        file_path.read_bytes(),
        mimetype="text/html"
    )
@app.route("/")
def home():
    with db() as con:
        reviews = con.execute(
            "SELECT customer_name, rating, review_text, created_at FROM reviews WHERE approved=1 ORDER BY id DESC LIMIT 30"
        ).fetchall()
    images = sorted([p.name for p in IMAGE_DIR.iterdir() if p.is_file() and p.suffix.lower().lstrip(".") in ALLOWED_IMAGES]) if IMAGE_DIR.exists() else []
    videos = sorted([p.name for p in VIDEO_DIR.iterdir() if p.is_file() and p.suffix.lower().lstrip(".") in ALLOWED_VIDEOS]) if VIDEO_DIR.exists() else []
    return render_template("index.html", reviews=reviews, images=images, videos=videos)

@app.route("/review", methods=["POST"])
def submit_review():
    name = request.form.get("customer_name", "").strip()[:80]
    rating = request.form.get("rating", "5")
    review_text = request.form.get("review_text", "").strip()[:1200]
    try:
        rating = int(rating)
    except ValueError:
        rating = 0
    if not name or not review_text or rating not in range(1, 6):
        flash("Please enter your name, choose a star rating, and write a review.", "error")
        return redirect(url_for("home") + "#reviews")
    with db() as con:
        con.execute("INSERT INTO reviews(customer_name, rating, review_text, approved) VALUES (?, ?, ?, 0)",
                    (name, rating, review_text))
    flash("Thanks! Your review was submitted and will appear after admin approval.", "success")
    return redirect(url_for("home") + "#reviews")

@app.route("/contact", methods=["POST"])
def contact():
    name = request.form.get("name", "").strip()[:100]
    phone = request.form.get("phone", "").strip()[:40]
    event_type = request.form.get("event_type", "").strip()[:100]
    event_date = request.form.get("event_date", "").strip()[:40]
    location = request.form.get("location", "").strip()[:160]
    message = request.form.get("message", "").strip()[:1200]
    if not name or not phone:
        flash("Please enter your name and phone number.", "error")
        return redirect(url_for("home") + "#contact")
    if not WHATSAPP_NUMBER:
        flash("WhatsApp number has not been configured yet. Add it to your environment settings.", "error")
        return redirect(url_for("home") + "#contact")
    text = f"Hello JMD Audio and Lightings!%0AName: {quote(name)}%0APhone: {quote(phone)}%0AEvent: {quote(event_type)}%0ADate: {quote(event_date)}%0ALocation: {quote(location)}%0ADetails: {quote(message)}"
    return redirect(f"https://wa.me/{WHATSAPP_NUMBER}?text={text}")

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST" and request.form.get("action") == "login":
        password = request.form.get("password", "")
        if secrets.compare_digest(password, ADMIN_PASSWORD):
            session["is_admin"] = True
            flash("Logged in successfully.", "success")
            return redirect(url_for("admin"))
        flash("Incorrect password.", "error")
    if not admin_required():
        return render_template("admin_login.html")
    with db() as con:
        reviews = con.execute("SELECT * FROM reviews ORDER BY approved ASC, id DESC").fetchall()
    images = sorted([p.name for p in IMAGE_DIR.iterdir() if p.is_file() and p.suffix.lower().lstrip(".") in ALLOWED_IMAGES])
    videos = sorted([p.name for p in VIDEO_DIR.iterdir() if p.is_file() and p.suffix.lower().lstrip(".") in ALLOWED_VIDEOS])
    return render_template("admin.html", reviews=reviews, images=images, videos=videos, max_upload_mb=MAX_UPLOAD_MB)

@app.route("/admin/upload", methods=["POST"])
def upload_media():
    if not admin_required():
        abort(403)
    kind = request.form.get("kind", "")
    uploaded = request.files.getlist("files")
    if kind not in {"image", "video"}:
        flash("Choose photos or videos first.", "error")
        return redirect(url_for("admin"))
    allowed = ALLOWED_IMAGES if kind == "image" else ALLOWED_VIDEOS
    target = IMAGE_DIR if kind == "image" else VIDEO_DIR
    target.mkdir(parents=True, exist_ok=True)
    count = 0
    for item in uploaded:
        if not item or not item.filename:
            continue
        safe = secure_filename(item.filename)
        if "." not in safe:
            continue
        ext = safe.rsplit(".", 1)[1].lower()
        if ext not in allowed:
            continue
        # Unique prefix avoids overwriting existing gallery items.
        stem = secure_filename(Path(safe).stem)[:60] or ("upload" if kind == "image" else "video")
        filename = f"{stem}_{secrets.token_hex(4)}.{ext}"
        item.save(target / filename)
        count += 1
    flash(f"Uploaded {count} {kind}(s)." if count else "No valid files uploaded.", "success" if count else "error")
    return redirect(url_for("admin"))

@app.route("/admin/review/<int:review_id>/<action>", methods=["POST"])
def manage_review(review_id, action):
    if not admin_required():
        abort(403)
    if action not in {"approve", "hide", "delete"}:
        abort(404)
    with db() as con:
        if action == "approve":
            con.execute("UPDATE reviews SET approved=1 WHERE id=?", (review_id,))
        elif action == "hide":
            con.execute("UPDATE reviews SET approved=0 WHERE id=?", (review_id,))
        else:
            con.execute("DELETE FROM reviews WHERE id=?", (review_id,))
    flash("Review updated.", "success")
    return redirect(url_for("admin") + "#reviews")

@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    return redirect(url_for("home"))

@app.errorhandler(413)
def too_large(_error):
    flash(f"File too large. Upload limit is {MAX_UPLOAD_MB} MB per request.", "error")
    return redirect(url_for("admin"))

init_db()

if __name__ == "__main__":
    app.run(debug=True)
