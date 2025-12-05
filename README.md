# Raspberry Pi Receipt Scanner & Catalog

A self-hosted receipt capture, OCR, and catalog system designed for Raspberry Pi with the AI camera module and MakerFocus UPS battery pack.

## Features
- Capture receipts via Raspberry Pi AI camera (libcamera) or upload images.
- OCR pipeline (pytesseract + OpenCV preprocessing) with heuristic parsing for dates, totals, tax, and vendor.
- Stores data in SQLite and exports a canonical `receipts.csv`.
- Responsive Flask web UI with dashboard, search/filtering, detail editing, and CSV export.
- Battery monitor loop for the MakerFocus UPS that triggers safe shutdown on low charge.
- Example `systemd` unit files for running the web app and battery daemon on boot.

## Hardware & OS Assumptions
- Raspberry Pi 4B or 5 running Raspberry Pi OS.
- Raspberry Pi AI Camera Module enabled via `libcamera` stack.
- MakerFocus Raspberry Pi 4 Battery Pack UPS, V3Plus Expansion Board (assumes INA219 fuel gauge over I2C address `0x40`).

## Setup
### Enable camera
```bash
sudo raspi-config # Interfaces -> enable Camera
sudo reboot
```
Verify capture:
```bash
libcamera-still -o test.jpg
```

### System packages
```bash
sudo apt update
sudo apt install -y python3-pip python3-venv tesseract-ocr libtesseract-dev libopenblas-dev libatlas-base-dev libjpeg-dev zlib1g-dev libcamera-apps
```
For I2C battery monitor:
```bash
sudo apt install -y python3-smbus i2c-tools
sudo raspi-config # Interface Options -> I2C -> enable
```

### Python environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### First run (development)
```bash
export FLASK_APP=app/main_app.py
flask run --host=0.0.0.0 --port=5000
```
Access from another device on LAN: `http://<pi-ip>:5000`.

### Production with gunicorn
```bash
source /home/pi/Raspberry-receipt-scanner/.venv/bin/activate
cd /home/pi/Raspberry-receipt-scanner
gunicorn --workers 3 --bind 0.0.0.0:5000 app.main_app:app
```

### systemd services
Copy the provided units and enable:
```bash
sudo cp systemd/receipt_web.service /etc/systemd/system/
sudo cp systemd/battery_monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable receipt_web.service battery_monitor.service
sudo systemctl start receipt_web.service battery_monitor.service
```
Ensure the `User` and `WorkingDirectory` paths in the unit files match your setup.

### Battery monitor
The default implementation reads voltage/current from an INA219-like device on I2C bus 1 at address `0x40`. Adjust `INA219_ADDRESS`, scaling, or `shutdown` command inside `app/battery_monitor.py` if your board differs.
Run manually for testing:
```bash
python3 battery_daemon.py
```
A `battery.log` file records readings; shutdown triggers when percentage falls below 10% by default.

### Camera capture
The app uses `libcamera-still` to capture images into `app/captured_receipts/`. Ensure the `libcamera-still` command works for your camera. If running on a non-Pi host, the capture function creates a placeholder image file for development.

### Data locations
- Database: `receipts.db`
- CSV export: `receipts.csv`
- Captured/uploaded images: `app/captured_receipts/`

### Permissions
- Camera access: ensure your user is in the `video` group.
- Shutdown command: the battery daemon runs `sudo shutdown -h now` by default. Configure `sudoers` to allow passwordless shutdown for the service user if needed.

## OCR pipeline
1. Capture/upload image.
2. Preprocess (grayscale, blur, Otsu threshold, deskew).
3. Run Tesseract OCR via `pytesseract`.
4. Parse heuristics for dates, totals, tax, currency, and vendor; store raw OCR text.
5. Persist to SQLite and refresh `receipts.csv` for easy export.

## Project structure
```
app/
  __init__.py
  main.py            # Flask routes
  main_app.py        # Entrypoint for flask/gunicorn
  camera.py          # libcamera capture helper
  ocr.py             # OCR + parsing logic
  models.py          # SQLite + CSV helpers
  battery_monitor.py # UPS monitoring
  templates/
  static/
app/captured_receipts/ # Image storage
battery_daemon.py       # Battery monitor loop
systemd/                # Example unit files
requirements.txt
receipts.db / receipts.csv (created on first run)
```

## Backups & exports
Use the web UI "Export CSV" link to download `receipts.csv`. You can also back up `receipts.db` and the `app/captured_receipts` folder for full fidelity.

## Troubleshooting
- If OCR results are poor, ensure good lighting, clean lens, and flat receipts. You can tweak preprocessing in `app/ocr.py`.
- For battery readings returning `None`, confirm I2C address and wiring with `i2cdetect -y 1`.
- If shutdown permission fails, adjust `SHUTDOWN_COMMAND` or sudoers for the service user.
