import os
import uuid
from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from .camera import capture_receipt
from .models import (
    delete_receipt,
    export_to_csv,
    get_receipt,
    insert_receipt,
    list_receipts,
    stats,
    timestamp_now,
    update_receipt,
)
from .ocr import process_image

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    summary = stats(current_app.config["DATABASE_PATH"])
    return render_template("index.html", summary=summary)


@bp.route("/receipts")
def receipt_list():
    page = int(request.args.get("page", 1))
    search = request.args.get("search")
    category = request.args.get("category")
    rows, total = list_receipts(
        current_app.config["DATABASE_PATH"], search=search, category=category, page=page
    )
    per_page = 10
    return render_template(
        "receipts.html",
        receipts=rows,
        total=total,
        page=page,
        per_page=per_page,
        search=search,
        category=category,
    )


@bp.route("/receipts/<receipt_id>", methods=["GET", "POST"])
def receipt_detail(receipt_id):
    if request.method == "POST":
        updates = {k: request.form.get(k) for k in request.form.keys()}
        updates["updated_at"] = timestamp_now()
        update_receipt(current_app.config["DATABASE_PATH"], receipt_id, updates)
        export_to_csv(current_app.config["DATABASE_PATH"], current_app.config["CSV_PATH"])
        flash("Receipt updated.", "success")
        return redirect(url_for("main.receipt_detail", receipt_id=receipt_id))

    receipt = get_receipt(current_app.config["DATABASE_PATH"], receipt_id)
    if not receipt:
        flash("Receipt not found", "danger")
        return redirect(url_for("main.receipt_list"))
    return render_template("receipt_detail.html", receipt=receipt)


@bp.route("/scan", methods=["GET", "POST"])
def scan():
    if request.method == "POST":
        image_dir = current_app.config["IMAGE_DIR"]
        os.makedirs(image_dir, exist_ok=True)
        filename = f"{uuid.uuid4()}.jpg"
        image_path = os.path.join(image_dir, filename)
        capture_receipt(image_path)

        parsed = process_image(image_path)
        receipt_id = parsed.get("id") or str(uuid.uuid4())
        now = timestamp_now()
        record = {
            "id": receipt_id,
            "date": parsed.get("date") or datetime.now().date().isoformat(),
            "vendor": parsed.get("vendor") or "Unknown",
            "total_amount": parsed.get("total_amount") or 0.0,
            "tax_amount": parsed.get("tax_amount") or 0.0,
            "currency": parsed.get("currency") or "USD",
            "payment_method": parsed.get("payment_method") or "Unknown",
            "category": parsed.get("category") or "Uncategorized",
            "notes": parsed.get("notes") or "",
            "image_path": os.path.relpath(image_path, start="."),
            "raw_text": parsed.get("raw_text") or "",
            "created_at": now,
            "updated_at": now,
        }
        insert_receipt(current_app.config["DATABASE_PATH"], record)
        export_to_csv(current_app.config["DATABASE_PATH"], current_app.config["CSV_PATH"])
        flash("Receipt captured and processed.", "success")
        return redirect(url_for("main.receipt_detail", receipt_id=receipt_id))
    return render_template("scan.html")


@bp.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        file = request.files.get("image")
        if not file:
            flash("No file uploaded", "danger")
            return redirect(request.url)
        image_dir = current_app.config["IMAGE_DIR"]
        os.makedirs(image_dir, exist_ok=True)
        filename = f"{uuid.uuid4()}_{file.filename}"
        path = os.path.join(image_dir, filename)
        file.save(path)
        parsed = process_image(path)
        receipt_id = parsed.get("id") or str(uuid.uuid4())
        now = timestamp_now()
        record = {
            "id": receipt_id,
            "date": parsed.get("date") or datetime.now().date().isoformat(),
            "vendor": parsed.get("vendor") or "Unknown",
            "total_amount": parsed.get("total_amount") or 0.0,
            "tax_amount": parsed.get("tax_amount") or 0.0,
            "currency": parsed.get("currency") or "USD",
            "payment_method": parsed.get("payment_method") or "Unknown",
            "category": parsed.get("category") or "Uncategorized",
            "notes": parsed.get("notes") or "",
            "image_path": os.path.relpath(path, start="."),
            "raw_text": parsed.get("raw_text") or "",
            "created_at": now,
            "updated_at": now,
        }
        insert_receipt(current_app.config["DATABASE_PATH"], record)
        export_to_csv(current_app.config["DATABASE_PATH"], current_app.config["CSV_PATH"])
        flash("Receipt uploaded and processed.", "success")
        return redirect(url_for("main.receipt_detail", receipt_id=receipt_id))
    return render_template("upload.html")


@bp.route("/export/csv")
def download_csv():
    export_to_csv(current_app.config["DATABASE_PATH"], current_app.config["CSV_PATH"])
    return send_file(current_app.config["CSV_PATH"], as_attachment=True)


@bp.route("/receipts/<receipt_id>/delete", methods=["POST"])
def remove_receipt(receipt_id):
    receipt = get_receipt(current_app.config["DATABASE_PATH"], receipt_id)
    if not receipt:
        flash("Receipt not found", "danger")
        return redirect(url_for("main.receipt_list"))
    delete_receipt(current_app.config["DATABASE_PATH"], receipt_id)
    export_to_csv(current_app.config["DATABASE_PATH"], current_app.config["CSV_PATH"])
    if receipt.get("image_path"):
        img_path = receipt["image_path"]
        if os.path.exists(img_path):
            os.remove(img_path)
    flash("Receipt deleted", "info")
    return redirect(url_for("main.receipt_list"))


@bp.route("/images/<path:filename>")
def serve_image(filename):
    return send_file(os.path.join(".", filename))
