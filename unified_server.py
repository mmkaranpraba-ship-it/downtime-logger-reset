from flask import Flask, send_file, request, jsonify, Response
import re
from datetime import datetime, timezone, timedelta
import csv
from io import StringIO

app = Flask(__name__)

downtime_events = []

IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_timestamp():
    return datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p")

NAME_MAP = {
    "cnc": "CNC Machine",
    "cnc machine": "CNC Machine",
    "lathe": "Lathe Machine",
    "lathe machine": "Lathe Machine",
    "grinder": "Grinder",
    "grinder machine": "Grinder",
    "machine 1": "CNC Machine",
    "machine 2": "Lathe Machine",
    "machine 3": "Grinder",
    "1": "CNC Machine",
    "2": "Lathe Machine",
    "3": "Grinder",
}

def extract_downtime_info(text):
    text_lower = text.lower()
    result = {"machine": None, "cause": "unknown"}
    
    # First, find machine name/number
    for key, display_name in NAME_MAP.items():
        if key in text_lower:
            result["machine"] = display_name
            # Extract remaining text as cause
            remaining = re.sub(rf'\b{re.escape(key)}\b', '', text_lower, flags=re.IGNORECASE).strip()
            # Remove common stop words
            remaining = re.sub(r'^(stopped|down|failed|issue|problem|band|off)\s*', '', remaining)
            if remaining:
                result["cause"] = remaining[:100]
            break
    
    # Fallback to keyword matching if no cause extracted
    if result["cause"] == "unknown":
        if "bearing" in text_lower:
            result["cause"] = "bearing failure"
        elif "motor" in text_lower:
            result["cause"] = "motor failure"
        elif "power" in text_lower or "bijli" in text_lower or "electric" in text_lower:
            result["cause"] = "power failure"
        elif "belt" in text_lower:
            result["cause"] = "belt broken"
        elif "operator" in text_lower or "chai" in text_lower or "absent" in text_lower:
            result["cause"] = "operator absent"
    
    return result

@app.route('/')
def dashboard():
    return send_file('dashboard.html')

@app.route('/shopfloor')
def shopfloor():
    return send_file('voice_recorder.html')

@app.route('/worker')
def worker_redirect():
    return send_file('voice_recorder.html')

@app.route('/whatsapp', methods=['POST'])
def whatsapp_webhook():
    incoming_msg = request.values.get("Body", "").lower()
    extracted = extract_downtime_info(incoming_msg)
    if extracted["machine"]:
        downtime_events.append({
            "machine": extracted["machine"],
            "cause": extracted["cause"],
            "timestamp": get_ist_timestamp()
        })
        return f"✅ {extracted['machine']} downtime logged at {get_ist_timestamp()}. Cause: {extracted['cause']}"
    else:
        return "❌ Please say machine name or number, e.g., 'CNC machine stopped, power failure'"

@app.route('/get_events')
def get_events():
    return jsonify({"events": downtime_events})

@app.route('/reset')
def reset():
    downtime_events.clear()
    return jsonify({"status": "reset"})

@app.route('/reset_machine', methods=['POST'])
def reset_machine():
    data = request.get_json()
    machine_name = data.get('machine')
    if not machine_name:
        return jsonify({"error": "Machine name required"}), 400
    global downtime_events
    downtime_events = [e for e in downtime_events if e['machine'] != machine_name]
    return jsonify({"status": f"Reset {machine_name}"})

@app.route('/export')
def export_csv():
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(["Timestamp", "Machine", "Cause", "Loss (₹/hour)"])
    
    cost_map = {"CNC Machine": 8000, "Lathe Machine": 6000, "Grinder": 4000}
    for event in downtime_events:
        loss = cost_map.get(event['machine'], 0)
        cw.writerow([event['timestamp'], event['machine'], event['cause'], loss])
    
    output = si.getvalue()
    return Response(output, mimetype='text/csv', headers={"Content-Disposition": "attachment;filename=downtime_report.csv"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)