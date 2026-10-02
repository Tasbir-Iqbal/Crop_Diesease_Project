from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3
import os
import uuid
import json
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from ultralytics import YOLO


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"), static_folder=os.path.join(BASE_DIR, "static"))
app.secret_key = os.environ.get("FIELDScan_SECRET_KEY", "fieldscan-secret-key")

app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "uploads")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

DATABASE = os.path.join(BASE_DIR, "FieldScan.db")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        first_name = request.form.get("first-name", "").strip()
        last_name = request.form.get("last-name", "").strip()
        email = request.form.get("email", "").strip().lower()
        primary_crop = request.form.get("primary-crop", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm-password", "")

        if not first_name or not last_name:
            flash("First name and last name are required.", "error")
            return redirect(url_for("register"))
        if not email:
            flash("Email address is required.", "error")
            return redirect(url_for("register"))
        if not primary_crop:
            flash("Please select your primary crop.", "error")
            return redirect(url_for("register"))
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return redirect(url_for("register"))
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("register"))

        conn = get_db()
        try:
            existing_user = conn.execute(
                "SELECT id FROM users WHERE email = ?", (email,)
            ).fetchone()

            if existing_user:
                flash("An account with this email already exists.", "error")
                return redirect(url_for("register"))

            conn.execute(
                """
                INSERT INTO users
                    (first_name, last_name, email, primary_crop, password)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    first_name,
                    last_name,
                    email,
                    primary_crop,
                    generate_password_hash(password),
                ),
            )
            conn.commit()
        finally:
            conn.close()

        flash("Account created successfully. Welcome to FieldScan!", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db()
        try:
            user = conn.execute(
                "SELECT * FROM users WHERE email = ?", (email,)
            ).fetchone()
        finally:
            conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = f'{user["first_name"]} {user["last_name"]}'.strip()
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT * FROM users WHERE id = ?", (session["user_id"],)
        ).fetchone()
    finally:
        conn.close()

    if user is None:
        session.clear()
        return redirect(url_for("login"))

    return render_template("dashboard.html", user=user)


MODEL_PATH = os.environ.get(
    "MODEL_PATH",
    os.path.join(BASE_DIR, "runs", "classify", "train", "weights", "best.pt"),
)

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(
        f"Model weights not found at {MODEL_PATH}. Run training or set MODEL_PATH."
    )

model = YOLO(MODEL_PATH)
print(f"Loaded model from: {MODEL_PATH}")


@app.route("/api/analyze", methods=["POST"])
def analyze_leaf():
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Please log in first."}), 401

    if "image" not in request.files:
        return jsonify({"success": False, "error": "No image uploaded."}), 400

    image = request.files["image"]
    if image.filename == "":
        return jsonify({"success": False, "error": "Please select an image."}), 400

    crop = request.form.get("crop", "").strip()
    field = request.form.get("field", "").strip()

    allowed_extensions = {"jpg", "jpeg", "png", "webp"}
    original_filename = secure_filename(image.filename)

    if "." not in original_filename:
        return jsonify({"success": False, "error": "Invalid image filename."}), 400

    extension = original_filename.rsplit(".", 1)[-1].lower()
    if extension not in allowed_extensions:
        return jsonify({"success": False, "error": "Only JPG, PNG and WEBP images are allowed."}), 400

    unique_filename = f"leaf_{uuid.uuid4().hex}.{extension}"
    image_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
    image.save(image_path)
    print("Image saved:", image_path)

    try:
        results = model(image_path)
        result = results[0]

        if result.probs is None:
            raise ValueError("Model did not return classification probabilities.")

        top1_idx = int(result.probs.top1)
        top1_conf = float(result.probs.top1conf.item())
        disease = result.names[top1_idx]
        confidence = round(top1_conf * 100, 2)

        top5_predictions = []
        for idx, conf in zip(result.probs.top5, result.probs.top5conf.tolist()):
            top5_predictions.append(
                {
                    "class": result.names[int(idx)],
                    "confidence": round(float(conf) * 100, 2),
                }
            )

        print(f"Top1 prediction: {disease} ({confidence}%)")

    except Exception as exc:
        print("YOLO error:", exc)
        if os.path.exists(image_path):
            os.remove(image_path)
        return jsonify({"success": False, "error": f"Image analysis failed: {exc}"}), 500

    latin = ""
    spread_risk = "Unknown"
    note = f"Detected {disease} with {confidence:.2f}% confidence."
    treatment = []

    user_id = session["user_id"]
    user_name = session.get("user_name", "User")

    conn = get_db()
    try:
        cursor = conn.execute(
            """
            INSERT INTO leaf_scans (
                user_id, user_name, image_filename, image_path,
                crop, field, disease, confidence, latin, spread_risk,
                note, treatment, top5
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                user_name,
                original_filename,
                image_path,
                crop,
                field,
                disease,
                confidence,
                latin,
                spread_risk,
                note,
                json.dumps(treatment),
                json.dumps(top5_predictions),
            ),
        )
        scan_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()

    return jsonify(
        {
            "success": True,
            "scan_id": scan_id,
            "user_id": user_id,
            "user_name": user_name,
            "image_filename": original_filename,
            "image_path": image_path,
            "crop": crop,
            "field": field,
            "disease": disease,
            "confidence": confidence,
            "latin": latin,
            "spread_risk": spread_risk,
            "note": note,
            "treatment": treatment,
            "top5": top5_predictions,
        }
    )


@app.route("/api/history", methods=["GET"])
def get_history():
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Please log in first."}), 401

    conn = get_db()
    try:
        scans = conn.execute(
            """
            SELECT
                id, user_name, image_filename, image_path,
                crop, field, disease, confidence, latin,
                spread_risk, note, treatment, top5, created_at
            FROM leaf_scans
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (session["user_id"],),
        ).fetchall()

        history = []
        for scan in scans:
            item = dict(scan)
            try:
                item["treatment"] = json.loads(item.get("treatment") or "[]")
            except (TypeError, json.JSONDecodeError):
                item["treatment"] = []
            try:
                item["top5"] = json.loads(item.get("top5") or "[]")
            except (TypeError, json.JSONDecodeError):
                item["top5"] = []
            history.append(item)

        return jsonify({"success": True, "scans": history})

    except sqlite3.Error as exc:
        print("HISTORY DATABASE ERROR:", exc)
        return jsonify({"success": False, "error": "Could not load scan history."}), 500
    finally:
        conn.close()

# =========================================================
# PDF REPORT
# =========================================================

@app.route("/api/report/<int:scan_id>", methods=["GET"])
def download_report(scan_id):
    if "user_id" not in session:
        return jsonify({
            "success": False,
            "error": "Please log in first."
        }), 401

    conn = get_db()

    try:
        scan = conn.execute(
            """
            SELECT *
            FROM leaf_scans
            WHERE id = ?
              AND user_id = ?
            """,
            (scan_id, session["user_id"])
        ).fetchone()
    finally:
        conn.close()

    if scan is None:
        return jsonify({
            "success": False,
            "error": "Scan not found."
        }), 404

    try:
        import io
        import json
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
            Image as ReportLabImage
        )
        from reportlab.lib import colors
        from flask import send_file

        pdf_buffer = io.BytesIO()

        document = SimpleDocTemplate(
            pdf_buffer,
            pagesize=A4,
            rightMargin=45,
            leftMargin=45,
            topMargin=45,
            bottomMargin=45
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Title"],
            alignment=TA_CENTER,
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#24462a"),
            spaceAfter=16
        )

        heading_style = ParagraphStyle(
            "ReportHeading",
            parent=styles["Heading2"],
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#24462a"),
            spaceBefore=10,
            spaceAfter=6
        )

        normal_style = ParagraphStyle(
            "ReportNormal",
            parent=styles["BodyText"],
            fontSize=10,
            leading=14
        )

        story = []

        story.append(Paragraph("FieldScan AI", title_style))
        story.append(Paragraph("Crop Disease Detection Report", styles["Heading2"]))
        story.append(Spacer(1, 12))

        confidence = scan["confidence"]
        confidence_text = (
            f"{float(confidence):.2f}%"
            if confidence is not None
            else "Unknown"
        )

        disease = (scan["disease"] or "Unknown").replace("_", " ")

        details = [
            ["Report ID", str(scan["id"])],
            ["Date", str(scan["created_at"] or "Unknown")],
            ["User", str(scan["user_name"] or "Unknown")],
            ["Field", str(scan["field"] or "Unknown")],
            ["Selected Crop", str(scan["crop"] or "Unknown")],
            ["AI Prediction", disease],
            ["Confidence", confidence_text],
            ["Spread Risk", str(scan["spread_risk"] or "Unknown")],
        ]

        details_table = Table(details, colWidths=[1.6 * inch, 4.8 * inch])

        details_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e9f0df")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#24462a")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c8d2bc")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ])
        )

        story.append(details_table)
        story.append(Spacer(1, 14))

        image_path = scan["image_path"]

        if image_path and os.path.exists(image_path):
            try:
                report_image = ReportLabImage(
                    image_path,
                    width=4.5 * inch,
                    height=3.2 * inch,
                    preserveAspectRatio=True,
                    anchor="c"
                )
                story.append(Paragraph("Uploaded Image", heading_style))
                story.append(report_image)
                story.append(Spacer(1, 12))
            except Exception as image_error:
                story.append(
                    Paragraph(
                        f"Image could not be included: {image_error}",
                        normal_style
                    )
                )

        story.append(Paragraph("Result Note", heading_style))
        story.append(
            Paragraph(
                str(scan["note"] or "No result note available."),
                normal_style
            )
        )

        story.append(Paragraph("Recommended Treatment", heading_style))

        try:
            treatment_items = json.loads(scan["treatment"] or "[]")
        except (TypeError, json.JSONDecodeError):
            treatment_items = []

        if treatment_items:
            for item in treatment_items:
                story.append(Paragraph(f"• {item}", normal_style))
                story.append(Spacer(1, 4))
        else:
            story.append(
                Paragraph(
                    "No treatment recommendation has been added for this prediction yet.",
                    normal_style
                )
            )

        story.append(Spacer(1, 18))
        story.append(
            Paragraph(
                "Disclaimer: This AI result is for educational and decision-support purposes only. "
                "It is not a guaranteed diagnosis. Consult a qualified agricultural expert before "
                "taking treatment action.",
                ParagraphStyle(
                    "Disclaimer",
                    parent=normal_style,
                    fontSize=8,
                    textColor=colors.HexColor("#666666")
                )
            )
        )

        document.build(story)
        pdf_buffer.seek(0)

        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"fieldscan_report_{scan_id}.pdf"
        )

    except Exception as error:
        print("PDF REPORT ERROR:", error)
        return jsonify({
            "success": False,
            "error": f"Could not generate PDF report: {error}"
        }), 500

import g4f


def call_model(prompt):
    try:
        response = g4f.ChatCompletion.create(
            model=g4f.models.default,
            messages=[{"role": "user", "content": prompt}],
        )
        return {"response": response}
    except Exception as exc:
        return {"error": str(exc)}


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True) or {}
    prompt = data.get("prompt", "")
    return jsonify(call_model(prompt))


@app.route("/upload_document", methods=["POST"])
def upload_document():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    filename = secure_filename(file.filename)
    ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""
    content = ""

    try:
        if ext == "pdf":
            import PyPDF2
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    content += text + "\n"
        elif ext == "docx":
            import docx
            document = docx.Document(file)
            for paragraph in document.paragraphs:
                content += paragraph.text + "\n"
        elif ext in {"txt", "md", "py", "js", "html", "css"}:
            content = file.read().decode("utf-8", errors="ignore")
        else:
            return jsonify({"error": f"Unsupported file type: {ext}"}), 400

        return jsonify({"content": content})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/settings", methods=["POST"])
def update_settings():
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Please log in first."}), 401

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()

    if not name:
        return jsonify({"success": False, "error": "Name is required."}), 400
    if not email or "@" not in email:
        return jsonify({"success": False, "error": "Enter a valid email."}), 400

    parts = name.split(maxsplit=1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""

    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ? AND id != ?",
            (email, session["user_id"]),
        ).fetchone()
        if existing:
            return jsonify({"success": False, "error": "This email is already being used."}), 409

        conn.execute(
            """
            UPDATE users
            SET first_name = ?, last_name = ?, email = ?
            WHERE id = ?
            """,
            (first_name, last_name, email, session["user_id"]),
        )
        conn.commit()
        session["user_name"] = name
        return jsonify({"success": True, "message": "Name and email updated successfully."})
    except sqlite3.Error as exc:
        conn.rollback()
        print("SETTINGS DATABASE ERROR:", exc)
        return jsonify({"success": False, "error": "Database error."}), 500
    finally:
        conn.close()


@app.route("/api/settings/password", methods=["POST"])
def update_password():
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Please log in first."}), 401

    data = request.get_json(silent=True) or {}
    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")

    if not current_password or not new_password:
        return jsonify({"success": False, "error": "Fill in all password fields."}), 400
    if len(new_password) < 8:
        return jsonify({"success": False, "error": "New password must be at least 8 characters."}), 400

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT password FROM users WHERE id = ?", (session["user_id"],)
        ).fetchone()
        if not user:
            return jsonify({"success": False, "error": "User not found."}), 404
        if not check_password_hash(user["password"], current_password):
            return jsonify({"success": False, "error": "Current password is incorrect."}), 400
        if check_password_hash(user["password"], new_password):
            return jsonify({"success": False, "error": "New password must be different."}), 400

        conn.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (generate_password_hash(new_password), session["user_id"]),
        )
        conn.commit()
        return jsonify({"success": True, "message": "Password updated successfully."})
    finally:
        conn.close()


@app.route("/api/settings/billing", methods=["POST"])
def update_billing():
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Please log in first."}), 401

    data = request.get_json(silent=True) or {}
    card_name = str(data.get("card_name", "")).strip()
    card_number = str(data.get("card_number", "")).replace(" ", "")
    cvc = str(data.get("cvc", "")).strip()
    expiry = str(data.get("expiry", "")).strip()

    if not card_name:
        return jsonify({"success": False, "error": "Enter the name on the card."}), 400
    if not card_number.isdigit() or not 13 <= len(card_number) <= 16:
        return jsonify({"success": False, "error": "Invalid card number."}), 400
    if len(cvc) not in (3, 4) or not cvc.isdigit():
        return jsonify({"success": False, "error": "Enter a valid CVC."}), 400

    try:
        month, year = expiry.split("/")
        if not 1 <= int(month) <= 12 or len(year) != 2:
            raise ValueError
    except (ValueError, AttributeError):
        return jsonify({"success": False, "error": "Enter expiry as MM/YY."}), 400

    conn = get_db()
    try:
        last4 = card_number[-4:]
        conn.execute(
            """
            INSERT INTO user_settings (user_id, card_name, card_last4)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                card_name = excluded.card_name,
                card_last4 = excluded.card_last4,
                updated_at = CURRENT_TIMESTAMP
            """,
            (session["user_id"], card_name, last4),
        )
        conn.commit()
        return jsonify({"success": True, "message": "Card saved.", "last4": last4})
    finally:
        conn.close()


@app.route("/api/account", methods=["DELETE"])
def delete_account():
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Please log in first."}), 401

    user_id = session["user_id"]
    conn = get_db()
    try:
        user = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return jsonify({"success": False, "error": "User not found."}), 404

        conn.execute("DELETE FROM leaf_scans WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM user_settings WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        session.clear()
        return jsonify({"success": True, "message": "Account deleted successfully."})
    except Exception as exc:
        conn.rollback()
        print("Delete account error:", exc)
        return jsonify({"success": False, "error": "Could not delete account."}), 500
    finally:
        conn.close()


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    print("Starting Flask server...")
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
        use_reloader=False
    )
