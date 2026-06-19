import os
import secrets
from datetime import datetime
from functools import wraps
from pathlib import Path

import joblib
import pymysql
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
from werkzeug.security import check_password_hash, generate_password_hash

from database import db

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "model" / "readmission_model.pkl"
METADATA_PATH = BASE_DIR / "model" / "model_metadata.pkl"

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
_db_seeded = False


@app.template_filter("datetime_short")
def datetime_short(value):
    if not value:
        return "—"
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)[:16]


def load_model():
    if not MODEL_PATH.exists() or not METADATA_PATH.exists():
        return None, None, None
    try:
        bundle = joblib.load(MODEL_PATH)
        metadata = joblib.load(METADATA_PATH)
        return bundle["model"], bundle["encoders"], metadata
    except (ValueError, ImportError, AttributeError) as e:
        raise RuntimeError(
            "Saved model is incompatible with this environment. "
            "Run `python train_model.py` to retrain."
        ) from e


def risk_level(score, thresholds):
    if score >= thresholds["high"]:
        return "High"
    if score >= thresholds["medium"]:
        return "Medium"
    return "Low"


def predict_readmission(features):
    model, encoders, metadata = load_model()
    if model is None:
        raise RuntimeError("Model not trained. Run train_model.py first.")

    import pandas as pd

    row = {col: features.get(col) for col in metadata["feature_columns"]}
    df = pd.DataFrame([row])

    for col in metadata["categorical_columns"]:
        le = encoders[col]
        val = str(df.at[0, col])
        if val not in le.classes_:
            val = le.classes_[0]
        df.at[0, col] = le.transform([val])[0]

    prob = float(model.predict_proba(df)[0][1])
    level = risk_level(prob, metadata["risk_thresholds"])
    return prob, level


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated


@app.before_request
def ensure_db():
    global _db_seeded
    db.ensure_ready()
    if not _db_seeded:
        _seed_default_user()
        _db_seeded = True


def _seed_default_user():
    existing = db.query_one("SELECT id FROM users WHERE username = ?", ("admin",))
    if existing:
        return
    db.execute(
        """INSERT INTO users (username, password, full_name, role, email)
           VALUES (?, ?, ?, ?, ?)""",
        (
            "admin",
            generate_password_hash("admin123"),
            "System Administrator",
            "admin",
            "admin@hospital.local",
        ),
    )


@app.context_processor
def inject_globals():
    return {
        "current_user": {
            "id": session.get("user_id"),
            "username": session.get("username"),
            "full_name": session.get("full_name"),
            "role": session.get("role"),
        }
    }


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = db.query_one("SELECT * FROM users WHERE username = ?", (username,))
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["full_name"] = user["full_name"]
            session["role"] = user["role"]
            db.execute(
                "UPDATE users SET last_login = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), user["id"]),
            )
            db.log_action(user["id"], "login", f"User {username} logged in")
            flash(f"Welcome back, {user['full_name']}!", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    if "user_id" in session:
        db.log_action(session["user_id"], "logout")
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    stats = db.get_dashboard_stats()
    recent = db.get_recent_predictions(8)
    monthly = db.get_monthly_predictions()
    return render_template(
        "dashboard.html",
        stats=stats,
        recent=recent,
        monthly=monthly,
    )


@app.route("/predict", methods=["GET", "POST"])
@login_required
def predict():
    patients = db.query_all(
        "SELECT patient_id, first_name, last_name FROM patients ORDER BY last_name"
    )
    result = None

    if request.method == "POST":
        try:
            features = {
                "age": int(request.form["age"]),
                "time_in_hospital": int(request.form["time_in_hospital"]),
                "num_lab_procedures": int(request.form["num_lab_procedures"]),
                "num_procedures": int(request.form["num_procedures"]),
                "num_medications": int(request.form["num_medications"]),
                "num_outpatient": int(request.form["num_outpatient"]),
                "num_inpatient": int(request.form["num_inpatient"]),
                "num_emergency": int(request.form["num_emergency"]),
                "gender": request.form["gender"],
                "medical_specialty": request.form["medical_specialty"],
                "primary_diagnosis": request.form["primary_diagnosis"],
                "insurance_type": request.form["insurance_type"],
            }
            patient_id = request.form.get("patient_id", "").strip()
            if not patient_id:
                raise ValueError("Please select a registered patient before running a prediction.")
            if not db.patient_id_exists(patient_id):
                raise ValueError(f"Patient ID '{patient_id}' was not found. Add the patient first.")

            prob, level = predict_readmission(features)
            pct = round(prob * 100, 1)

            db.execute("""
                INSERT INTO predictions
                (patient_id, time_in_hospital, num_lab_procedures, num_procedures,
                 num_medications, num_outpatient, num_inpatient, num_emergency,
                 readmission_risk, risk_level, predicted_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                patient_id,
                features["time_in_hospital"],
                features["num_lab_procedures"],
                features["num_procedures"],
                features["num_medications"],
                features["num_outpatient"],
                features["num_inpatient"],
                features["num_emergency"],
                pct,
                level,
                session["user_id"],
            ))
            db.log_action(session["user_id"], "prediction", f"Risk {level} for {patient_id}")

            result = {"risk_pct": pct, "risk_level": level, "patient_id": patient_id}
            flash("Prediction completed successfully.", "success")
        except Exception as e:
            flash(f"Prediction failed: {e}", "danger")

    try:
        _, _, metadata = load_model()
    except RuntimeError as e:
        metadata = None
        flash(str(e), "danger")

    options = metadata.get("encoder_classes", {}) if metadata else {}

    return render_template(
        "predict.html",
        patients=patients,
        result=result,
        options=options,
    )


@app.route("/patients")
@login_required
def patients():
    search = request.args.get("q", "")
    page = max(1, int(request.args.get("page", 1)))
    rows, total = db.search_patients(search, page)
    per_page = 10
    total_pages = max(1, (total + per_page - 1) // per_page)

    return render_template(
        "patients.html",
        patients=rows,
        search=search,
        page=page,
        total_pages=total_pages,
        total=total,
    )


@app.route("/api/patients/next-id")
@login_required
def api_next_patient_id():
    return jsonify({"patient_id": db.generate_patient_id()})


@app.route("/api/patients", methods=["POST"])
@login_required
def api_create_patient():
    data = request.get_json() or {}
    required = ["first_name", "last_name", "date_of_birth", "gender"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"Missing field: {field}"}), 400

    patient_id = (data.get("patient_id") or "").strip()
    if not patient_id:
        patient_id = db.generate_patient_id()
    elif db.patient_id_exists(patient_id):
        return jsonify({"error": f"Patient ID '{patient_id}' already exists. Use a different ID or leave it blank to auto-generate one."}), 409

    try:
        db.execute("""
            INSERT INTO patients
            (patient_id, first_name, last_name, date_of_birth, gender,
             phone, email, address, insurance_type, primary_diagnosis, medical_specialty)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            patient_id,
            data["first_name"].strip(),
            data["last_name"].strip(),
            data["date_of_birth"],
            data["gender"],
            data.get("phone"),
            data.get("email"),
            data.get("address"),
            data.get("insurance_type"),
            data.get("primary_diagnosis"),
            data.get("medical_specialty"),
        ))
        db.log_action(session["user_id"], "create_patient", patient_id)
        return jsonify({"success": True, "patient_id": patient_id})
    except pymysql.err.IntegrityError:
        return jsonify({"error": f"Patient ID '{patient_id}' already exists."}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/patients/<patient_id>", methods=["DELETE"])
@login_required
def api_delete_patient(patient_id):
    db.execute("DELETE FROM patients WHERE patient_id = ?", (patient_id,))
    db.log_action(session["user_id"], "delete_patient", patient_id)
    return jsonify({"success": True})


@app.route("/analytics")
@login_required
def analytics():
    monthly = db.get_monthly_predictions()
    risk_breakdown = db.query_all("""
        SELECT risk_level, COUNT(*) AS count
        FROM predictions GROUP BY risk_level
    """)
    diagnosis_stats = db.query_all("""
        SELECT pt.primary_diagnosis AS diagnosis, COUNT(*) AS count,
               ROUND(AVG(p.readmission_risk), 1) AS avg_risk
        FROM predictions p
        JOIN patients pt ON p.patient_id = pt.patient_id
        WHERE pt.primary_diagnosis IS NOT NULL
        GROUP BY pt.primary_diagnosis
        ORDER BY count DESC
        LIMIT 8
    """)
    return render_template(
        "analytics.html",
        monthly=monthly,
        risk_breakdown=risk_breakdown,
        diagnosis_stats=diagnosis_stats,
    )


@app.route("/reports")
@login_required
def reports():
    predictions = db.query_all("""
        SELECT p.*, pt.first_name, pt.last_name, pt.primary_diagnosis
        FROM predictions p
        LEFT JOIN patients pt ON p.patient_id = pt.patient_id
        ORDER BY p.created_at DESC
        LIMIT 100
    """)
    return render_template("reports.html", predictions=predictions)


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "change_password":
            current = request.form.get("current_password", "")
            new_pass = request.form.get("new_password", "")
            confirm = request.form.get("confirm_password", "")

            user = db.query_one("SELECT * FROM users WHERE id = ?", (session["user_id"],))
            if not user or not check_password_hash(user["password"], current):
                flash("Current password is incorrect.", "danger")
            elif new_pass != confirm or len(new_pass) < 6:
                flash("New passwords must match and be at least 6 characters.", "danger")
            else:
                db.execute(
                    "UPDATE users SET password = ? WHERE id = ?",
                    (generate_password_hash(new_pass), session["user_id"]),
                )
                flash("Password updated successfully.", "success")

        elif action == "update_profile" and session.get("role") == "admin":
            full_name = request.form.get("full_name", "").strip()
            email = request.form.get("email", "").strip()
            if full_name:
                db.execute(
                    "UPDATE users SET full_name = ?, email = ? WHERE id = ?",
                    (full_name, email, session["user_id"]),
                )
                session["full_name"] = full_name
                flash("Profile updated.", "success")

    user = db.query_one("SELECT * FROM users WHERE id = ?", (session["user_id"],))
    try:
        _, _, metadata = load_model()
    except RuntimeError:
        metadata = None
    return render_template("settings.html", user=user, metadata=metadata)


@app.route("/api/stats")
@login_required
def api_stats():
    return jsonify({
        "dashboard": db.get_dashboard_stats(),
        "monthly": db.get_monthly_predictions(),
    })


if __name__ == "__main__":
    db.ensure_ready()
    _seed_default_user()
    app.run(debug=True, host="0.0.0.0", port=5000)