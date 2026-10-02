from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
    send_file
)

from io import BytesIO
import sqlite3
import os
import uuid
import json

from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from PIL import Image
import PyPDF2
import docx
from ultralytics import YOLO

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


app = Flask(__name__)
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "fieldscan-development-key"
)

app.config["UPLOAD_FOLDER"] = "uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

DATABASE = "FieldScan.db"


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
                "SELECT id FROM users WHERE email = ?",
                (email,)
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
                    generate_password_hash(password)
                )
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
                "SELECT * FROM users WHERE email = ?",
                (email,)
            ).fetchone()
        finally:
            conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = (
                f'{user["first_name"]} {user["last_name"]}'
            )

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
            "SELECT * FROM users WHERE id = ?",
            (session["user_id"],)
        ).fetchone()
    finally:
        conn.close()

    return render_template("dashboard.html", user=user)


# =========================================================
# MODELS AND DISEASE INFORMATION
# =========================================================

MODEL_PATH = os.environ.get(
    "MODEL_PATH",
    r"D:\Project\runs\classify\train\weights\best.pt"
)

GATE_MODEL_PATH = os.environ.get(
    "GATE_MODEL_PATH",
    r"D:\Project\runs\crop_gate_v1\weights\best.pt"
)


if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(
        f"Disease model not found at {MODEL_PATH}"
    )

if not os.path.exists(GATE_MODEL_PATH):
    raise FileNotFoundError(
        f"Crop gate model not found at {GATE_MODEL_PATH}"
    )


model = YOLO(MODEL_PATH)
gate_model = YOLO(GATE_MODEL_PATH)

print(f"Loaded disease model from: {MODEL_PATH}")
print(f"Loaded crop gate model from: {GATE_MODEL_PATH}")


DISEASE_INFO = {
    "Corn___Common_Rust": (
        "Corn / maize",
        "High",
        [
            "Inspect nearby corn plants for rust pustules.",
            "Manage volunteer corn and monitor the field closely.",
            "Use a locally approved fungicide only when recommended."
        ]
    ),

    "Corn___Gray_Leaf_Spot": (
        "Corn / maize",
        "High",
        [
            "Inspect nearby leaves for expanding lesions.",
            "Manage infected residue and rotate crops where practical.",
            "Use a locally approved fungicide according to the label."
        ]
    ),

    "Corn___Healthy": (
        "Corn / maize",
        "No",
        [
            "No disease treatment is indicated by this prediction.",
            "Continue regular scouting and crop management."
        ]
    ),

    "Corn___Northern_Leaf_Blight": (
        "Corn / maize",
        "High",
        [
            "Inspect surrounding plants for expanding lesions.",
            "Manage infected residue and rotate crops where practical.",
            "Use an approved fungicide according to local guidance."
        ]
    ),

    "Potato___Early_Blight": (
        "Potato",
        "Medium",
        [
            "Remove severely affected plant material where practical.",
            "Avoid overhead irrigation when possible.",
            "Use an approved fungicide according to the label."
        ]
    ),

    "Potato___Healthy": (
        "Potato",
        "No",
        [
            "No disease treatment is indicated by this prediction.",
            "Continue regular scouting and crop management."
        ]
    ),

    "Potato___Late_Blight": (
        "Potato",
        "High",
        [
            "Inspect the field promptly for additional lesions.",
            "Remove heavily infected material where practical.",
            "Seek local extension guidance before treatment."
        ]
    ),

    "Rice_BrownSpot": (
        "Rice",
        "Medium",
        [
            "Inspect nearby rice plants for additional lesions.",
            "Maintain balanced nutrition and reduce plant stress.",
            "Use locally approved treatment according to the label."
        ]
    ),

    "Rice_Healthy": (
        "Rice",
        "No",
        [
            "No disease treatment is indicated by this prediction.",
            "Continue regular scouting and crop management."
        ]
    ),

    "Rice_Hispa": (
        "Rice",
        "Medium",
        [
            "Inspect the field for additional leaf-scraping damage.",
            "Remove heavily affected leaves where practical.",
            "Use approved pest-management treatment according to the label."
        ]
    ),

    "Rice_LeafBlast": (
        "Rice",
        "High",
        [
            "Inspect nearby rice plants for diamond-shaped lesions.",
            "Avoid excessive nitrogen where possible.",
            "Use an approved fungicide according to local guidance."
        ]
    ),

    "Wheat_Aphid": (
        "Wheat",
        "Medium",
        [
            "Inspect the underside of leaves and nearby plants.",
            "Preserve beneficial insects where possible.",
            "Use locally approved pest control when justified."
        ]
    ),

    "Wheat_BlackRust": (
        "Wheat",
        "High",
        [
            "Scout the field for additional rust pustules.",
            "Consider resistant varieties for future planting.",
            "Seek local extension guidance on fungicide use."
        ]
    ),

    "Wheat_Blast": (
        "Wheat",
        "High",
        [
            "Inspect nearby plants and heads for similar symptoms.",
            "Remove heavily affected material where practical.",
            "Seek local agronomist guidance before treatment."
        ]
    ),

    "Wheat_BrownRust": (
        "Wheat",
        "Medium",
        [
            "Scout nearby plants for orange-brown rust pustules.",
            "Consider resistant varieties and balanced crop management.",
            "Use an approved fungicide only when recommended."
        ]
    ),

    "Wheat_CommonRootRot": (
        "Wheat",
        "Medium",
        [
            "Inspect roots and surrounding plants to confirm the diagnosis.",
            "Improve rotation and soil conditions where possible.",
            "Seek local extension guidance before treatment."
        ]
    ),

    "Wheat_FusariumHeadBlight": (
        "Wheat",
        "High",
        [
            "Inspect nearby heads during flowering and grain development.",
            "Use resistant varieties and rotation where practical.",
            "Follow local guidance for fungicide timing."
        ]
    ),

    "Wheat_Healthy": (
        "Wheat",
        "No",
        [
            "No disease treatment is indicated by this prediction.",
            "Continue regular scouting and crop management."
        ]
    ),

    "Wheat_LeafBlight": (
        "Wheat",
        "Medium",
        [
            "Inspect nearby leaves for expanding lesions.",
            "Improve residue management where practical.",
            "Use an approved fungicide according to local guidance."
        ]
    ),

    "Wheat_Mildew": (
        "Wheat",
        "Medium",
        [
            "Inspect nearby plants for white mildew growth.",
            "Improve airflow and avoid excessive nitrogen.",
            "Use a locally approved fungicide when recommended."
        ]
    ),

    "Wheat_Mite": (
        "Wheat",
        "Medium",
        [
            "Inspect leaves and nearby plants for mite activity.",
            "Reduce plant stress and preserve beneficial predators.",
            "Use approved miticide treatment when justified."
        ]
    ),

    "Wheat_Septoria": (
        "Wheat",
        "Medium",
        [
            "Inspect lower and upper leaves for expanding lesions.",
            "Manage crop residue and rotate crops where practical.",
            "Use an approved fungicide according to local guidance."
        ]
    ),

    "Wheat_Smut": (
        "Wheat",
        "High",
        [
            "Separate affected seed from healthy planting material.",
            "Use certified, disease-free seed in future planting.",
            "Seek local guidance on seed treatment."
        ]
    ),

    "Wheat_Stemfly": (
        "Wheat",
        "Medium",
        [
            "Inspect stems and nearby plants for additional damage.",
            "Remove volunteer wheat and manage field weeds.",
            "Use approved pest-management treatment if justified."
        ]
    ),

    "Wheat_Tanspot": (
        "Wheat",
        "Medium",
        [
            "Inspect nearby leaves for tan lesions.",
            "Manage crop residue and rotate crops where practical.",
            "Use an approved fungicide according to local guidance."
        ]
    ),

    "Wheat_YellowRust": (
        "Wheat",
        "High",
        [
            "Scout the field for yellow rust stripes.",
            "Consider resistant varieties and avoid plant stress.",
            "Seek local extension guidance on fungicide use."
        ]
    )
}


@app.route("/api/analyze", methods=["POST"])
def analyze_leaf():
    if "user_id" not in session:
        return jsonify({
            "success": False,
            "error": "Please log in first."
        }), 401

    if "image" not in request.files:
        return jsonify({
            "success": False,
            "error": "No image uploaded."
        }), 400

    image = request.files["image"]

    if image.filename == "":
        return jsonify({
            "success": False,
            "error": "Please select an image."
        }), 400

    selected_crop = request.form.get("crop", "").strip()
    field = request.form.get("field", "").strip()

    allowed_extensions = {
        "jpg",
        "jpeg",
        "png",
        "webp"
    }

    original_filename = secure_filename(image.filename)

    if "." not in original_filename:
        return jsonify({
            "success": False,
            "error": "Invalid image filename."
        }), 400

    extension = original_filename.rsplit(".", 1)[-1].lower()

    if extension not in allowed_extensions:
        return jsonify({
            "success": False,
            "error": "Only JPG, PNG and WEBP images are allowed."
        }), 400

    unique_filename = (
        f"leaf_{uuid.uuid4().hex}.{extension}"
    )

    image_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        unique_filename
    )

    image.save(image_path)

    print("Image saved:", image_path)

    try:
        gate_result = gate_model(image_path)[0]

        if gate_result.probs is None:
            raise ValueError(
                "Crop gate did not return probabilities."
            )

        gate_label = gate_result.names[
            gate_result.probs.top1
        ]

        if gate_label != "crop":
            if os.path.exists(image_path):
                os.remove(image_path)

            return jsonify({
                "success": False,
                "error": (
                    "This does not appear to be a crop image. "
                    "Please upload a crop photo."
                )
            }), 400

        result = model(image_path)[0]

        if result.probs is None:
            raise ValueError(
                "Disease model did not return probabilities."
            )

        top1_index = result.probs.top1
        confidence = round(
            result.probs.top1conf.item() * 100,
            2
        )

        disease = result.names[top1_index]

        top5_predictions = []

        for class_index, class_confidence in zip(
            result.probs.top5,
            result.probs.top5conf.tolist()
        ):
            top5_predictions.append({
                "class": result.names[class_index],
                "confidence": round(
                    class_confidence * 100,
                    2
                )
            })

        print(
            f"Top1 prediction: {disease} "
            f"({confidence}%)"
        )

    except Exception as exc:
        print("YOLO error:", exc)

        if os.path.exists(image_path):
            os.remove(image_path)

        return jsonify({
            "success": False,
            "error": f"Image analysis failed: {exc}"
        }), 500

    default_info = (
        "Unknown",
        "Low",
        [
            "Monitor the plant and nearby plants for changes.",
            "Confirm the result with a local agronomist."
        ]
    )

    detected_crop, spread_risk, treatment = DISEASE_INFO.get(
        disease,
        default_info
    )

    if selected_crop and selected_crop.lower() != "not sure":
        displayed_crop = selected_crop
    else:
        displayed_crop = detected_crop

    latin = ""

    note = (
        f"Detected {disease.replace('_', ' ')} "
        f"in {displayed_crop} "
        f"with {confidence:.2f}% confidence."
    )

    user_id = session["user_id"]
    user_name = session.get("user_name", "User")

    conn = get_db()

    try:
        cursor = conn.execute(
            """
            INSERT INTO leaf_scans (
                user_id,
                user_name,
                image_filename,
                image_path,
                crop,
                field,
                disease,
                confidence,
                latin,
                spread_risk,
                note,
                treatment,
                top5
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                user_name,
                original_filename,
                image_path,
                displayed_crop,
                field,
                disease,
                confidence,
                latin,
                spread_risk,
                note,
                json.dumps(treatment),
                json.dumps(top5_predictions)
            )
        )

        scan_id = cursor.lastrowid
        conn.commit()

    finally:
        conn.close()

    return jsonify({
        "success": True,
        "scan_id": scan_id,
        "user_id": user_id,
        "user_name": user_name,
        "image_filename": original_filename,
        "image_path": image_path,
        "crop": displayed_crop,
        "field": field,
        "disease": disease,
        "confidence": confidence,
        "latin": latin,
        "spread_risk": spread_risk,
        "note": note,
        "treatment": treatment,
        "top5": top5_predictions
    })

@app.route("/api/history", methods=["GET"])
def get_scan_history():
    if "user_id" not in session:
        return jsonify({
            "success": False,
            "error": "Please log in first."
        }), 401

    conn = get_db()

    try:
        scans = conn.execute(
            """
            SELECT
                id,
                user_id,
                user_name,
                image_filename,
                image_path,
                crop,
                field,
                disease,
                confidence,
                latin,
                spread_risk,
                note,
                treatment,
                top5,
                created_at
            FROM leaf_scans
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (session["user_id"],)
        ).fetchall()

    finally:
        conn.close()

    history = []

    for scan in scans:
        try:
            treatment = json.loads(scan["treatment"] or "[]")
        except (TypeError, json.JSONDecodeError):
            treatment = []

        try:
            top5 = json.loads(scan["top5"] or "[]")
        except (TypeError, json.JSONDecodeError):
            top5 = []

        history.append({
            "id": scan["id"],
            "scan_id": scan["id"],
            "user_id": scan["user_id"],
            "user_name": scan["user_name"],
            "image_filename": scan["image_filename"],
            "image_path": scan["image_path"],
            "crop": scan["crop"],
            "field": scan["field"],
            "disease": scan["disease"],
            "confidence": scan["confidence"],
            "latin": scan["latin"],
            "spread_risk": scan["spread_risk"],
            "note": scan["note"],
            "treatment": treatment,
            "top5": top5,
            "created_at": scan["created_at"]
        })

    return jsonify({
        "success": True,
        "history": history
    })

# =========================================================
# PDF REPORT DOWNLOAD
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
            "error": "Scan report not found."
        }), 404

    pdf_buffer = BytesIO()

    pdf = canvas.Canvas(
        pdf_buffer,
        pagesize=A4
    )

    width, height = A4
    y = height - 60

    pdf.setTitle("FieldScan AI Scan Report")

    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(
        50,
        y,
        "FieldScan AI - Scan Report"
    )

    y -= 45

    pdf.setFont("Helvetica", 11)

    pdf.drawString(
        50,
        y,
        f"Crop: {scan['crop'] or 'Not available'}"
    )

    y -= 22

    pdf.drawString(
        50,
        y,
        f"Field: {scan['field'] or 'Not available'}"
    )

    y -= 22

    disease_name = (
        scan["disease"] or "Not available"
    ).replace("_", " ")

    pdf.drawString(
        50,
        y,
        f"Diagnosis: {disease_name}"
    )

    y -= 22

    pdf.drawString(
        50,
        y,
        f"Confidence: {scan['confidence']}%"
    )

    y -= 22

    pdf.drawString(
        50,
        y,
        f"Spread risk: {scan['spread_risk'] or 'Not available'}"
    )

    y -= 35

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(
        50,
        y,
        "Notes"
    )

    y -= 22

    pdf.setFont("Helvetica", 11)

    note = scan["note"] or "No notes available."

    pdf.drawString(
        50,
        y,
        note[:110]
    )

    y -= 35

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(
        50,
        y,
        "Recommended treatment"
    )

    y -= 22

    pdf.setFont("Helvetica", 11)

    try:
        treatments = json.loads(
            scan["treatment"] or "[]"
        )

    except (TypeError, json.JSONDecodeError):
        treatments = []

    if treatments:
        for treatment in treatments:
            if y < 70:
                pdf.showPage()
                y = height - 60
                pdf.setFont("Helvetica", 11)

            pdf.drawString(
                65,
                y,
                f"- {str(treatment)[:100]}"
            )

            y -= 22

    else:
        pdf.drawString(
            65,
            y,
            "No treatment information available."
        )

        y -= 22

    pdf.setFont("Helvetica-Oblique", 9)

    pdf.drawString(
        50,
        40,
        "AI-assisted result. Confirm with a qualified agronomist."
    )

    pdf.save()
    pdf_buffer.seek(0)

    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"fieldscan_report_{scan_id}.pdf"
    )


# =========================================================
# AI ASSISTANT
# =========================================================

try:
    import g4f
except ImportError:
    g4f = None


def call_model(prompt):
    if g4f is None:
        return {
            "error": "The AI assistant dependency is not installed."
        }

    try:
        response = g4f.ChatCompletion.create(
            model=g4f.models.default,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return {
            "response": response
        }

    except Exception as exc:
        return {
            "error": str(exc)
        }


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True) or {}
    prompt = data.get("prompt", "")
    return jsonify(call_model(prompt))


# =========================================================
# DOCUMENT UPLOAD
# =========================================================

@app.route("/upload_document", methods=["POST"])
def upload_document():
    if "file" not in request.files:
        return jsonify({
            "error": "No file part"
        }), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({
            "error": "No selected file"
        }), 400

    filename = secure_filename(file.filename)

    if "." in filename:
        extension = filename.rsplit(".", 1)[-1].lower()
    else:
        extension = ""

    content = ""

    try:
        if extension == "pdf":
            reader = PyPDF2.PdfReader(file)

            for page in reader.pages:
                text = page.extract_text()

                if text:
                    content += text + "\n"

        elif extension == "docx":
            document = docx.Document(file)

            for paragraph in document.paragraphs:
                content += paragraph.text + "\n"

        elif extension in {
            "txt",
            "md",
            "py",
            "js",
            "html",
            "css"
        }:
            content = file.read().decode(
                "utf-8",
                errors="ignore"
            )

        else:
            return jsonify({
                "error": f"Unsupported file type: {extension}"
            }), 400

        return jsonify({
            "content": content
        })

    except Exception as exc:
        return jsonify({
            "error": str(exc)
        }), 500


# =========================================================
# SETTINGS
# =========================================================

@app.route("/api/settings", methods=["POST"])
def update_settings():
    if "user_id" not in session:
        return jsonify({
            "success": False,
            "error": "Please log in first."
        }), 401

    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()

    if not name:
        return jsonify({
            "success": False,
            "error": "Name is required."
        }), 400

    if not email or "@" not in email:
        return jsonify({
            "success": False,
            "error": "Enter a valid email."
        }), 400

    parts = name.split(maxsplit=1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""

    conn = get_db()

    try:
        existing = conn.execute(
            """
            SELECT id
            FROM users
            WHERE email = ?
              AND id != ?
            """,
            (email, session["user_id"])
        ).fetchone()

        if existing:
            return jsonify({
                "success": False,
                "error": "This email is already being used."
            }), 409

        conn.execute(
            """
            UPDATE users
            SET first_name = ?,
                last_name = ?,
                email = ?
            WHERE id = ?
            """,
            (
                first_name,
                last_name,
                email,
                session["user_id"]
            )
        )

        conn.commit()
        session["user_name"] = name

        return jsonify({
            "success": True,
            "message": "Name and email updated successfully."
        })

    finally:
        conn.close()


@app.route("/api/settings/password", methods=["POST"])
def update_password():
    if "user_id" not in session:
        return jsonify({
            "success": False,
            "error": "Please log in first."
        }), 401

    data = request.get_json(silent=True) or {}

    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")

    if not current_password or not new_password:
        return jsonify({
            "success": False,
            "error": "Fill in all password fields."
        }), 400

    if len(new_password) < 8:
        return jsonify({
            "success": False,
            "error": "New password must be at least 8 characters."
        }), 400

    conn = get_db()

    try:
        user = conn.execute(
            "SELECT password FROM users WHERE id = ?",
            (session["user_id"],)
        ).fetchone()

        if not user:
            return jsonify({
                "success": False,
                "error": "User not found."
            }), 404

        if not check_password_hash(
            user["password"],
            current_password
        ):
            return jsonify({
                "success": False,
                "error": "Current password is incorrect."
            }), 400

        conn.execute(
            """
            UPDATE users
            SET password = ?
            WHERE id = ?
            """,
            (
                generate_password_hash(new_password),
                session["user_id"]
            )
        )

        conn.commit()

        return jsonify({
            "success": True,
            "message": "Password updated successfully."
        })

    finally:
        conn.close()


@app.route("/api/settings/billing", methods=["POST"])
def update_billing():
    if "user_id" not in session:
        return jsonify({
            "success": False,
            "error": "Please log in first."
        }), 401

    data = request.get_json(silent=True) or {}

    card_name = str(
        data.get("card_name", "")
    ).strip()

    card_number = str(
        data.get("card_number", "")
    ).replace(" ", "")

    expiry = str(
        data.get("expiry", "")
    ).strip()

    cvc = str(
        data.get("cvc", "")
    ).strip()

    if not card_name:
        return jsonify({
            "success": False,
            "error": "Enter the name on the card."
        }), 400

    if not card_number.isdigit():
        return jsonify({
            "success": False,
            "error": "Enter a valid card number."
        }), 400

    if not 13 <= len(card_number) <= 16:
        return jsonify({
            "success": False,
            "error": "Enter a valid card number."
        }), 400

    if len(cvc) not in (3, 4) or not cvc.isdigit():
        return jsonify({
            "success": False,
            "error": "Enter a valid CVC."
        }), 400

    try:
        month, year = expiry.split("/")

        if not 1 <= int(month) <= 12:
            raise ValueError

        if len(year) != 2:
            raise ValueError

    except (ValueError, AttributeError):
        return jsonify({
            "success": False,
            "error": "Enter expiry as MM/YY."
        }), 400

    conn = get_db()

    try:
        last4 = card_number[-4:]

        conn.execute(
            """
            INSERT INTO user_settings
            (user_id, card_name, card_last4)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                card_name = excluded.card_name,
                card_last4 = excluded.card_last4,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                session["user_id"],
                card_name,
                last4
            )
        )

        conn.commit()

        return jsonify({
            "success": True,
            "message": "Card saved.",
            "last4": last4
        })

    finally:
        conn.close()


@app.route("/api/account", methods=["DELETE"])
def delete_account():
    if "user_id" not in session:
        return jsonify({
            "success": False,
            "error": "Please log in first."
        }), 401

    conn = get_db()

    try:
        user_id = session["user_id"]

        conn.execute(
            "DELETE FROM leaf_scans WHERE user_id = ?",
            (user_id,)
        )

        conn.execute(
            "DELETE FROM user_settings WHERE user_id = ?",
            (user_id,)
        )

        conn.execute(
            "DELETE FROM users WHERE id = ?",
            (user_id,)
        )

        conn.commit()
        session.clear()

        return jsonify({
            "success": True,
            "message": "Account deleted successfully."
        })

    except Exception:
        conn.rollback()

        return jsonify({
            "success": False,
            "error": "Could not delete account."
        }), 500

    finally:
        conn.close()


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    print("Starting Flask server...")

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000,
        use_reloader=False
    )