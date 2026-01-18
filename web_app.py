"""
Web interface for THSRC Ticket Bot
"""
import os
import logging
import threading
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
from functools import wraps

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'thsrc-ticket-bot-secret')

# Password protection
APP_PASSWORD = os.environ.get('APP_PASSWORD', '')

# Global state for booking status
booking_status = {
    'running': False,
    'logs': [],
    'result': None,
    'thread': None,
    'attempt': 0,
    'max_attempts': 50,  # Maximum auto-retry attempts
    'stop_requested': False
}

# Check Gemini API key availability
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>THSRC Ticket Bot</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 { font-size: 28px; margin-bottom: 8px; }
        .header p { opacity: 0.9; }
        .form-section {
            padding: 30px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #374151;
        }
        .form-group input, .form-group select {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e5e7eb;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.2s;
        }
        .form-group input:focus, .form-group select:focus {
            outline: none;
            border-color: #f97316;
        }
        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        .btn {
            display: inline-block;
            padding: 14px 28px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .btn:hover { transform: translateY(-2px); }
        .btn-primary {
            background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
            color: white;
            width: 100%;
        }
        .btn-primary:hover { box-shadow: 0 8px 20px rgba(249,115,22,0.4); }
        .btn-primary:disabled {
            background: #9ca3af;
            cursor: not-allowed;
            transform: none;
        }
        .log-section {
            background: #1f2937;
            color: #10b981;
            padding: 20px;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 13px;
            max-height: 400px;
            overflow-y: auto;
            display: none;
        }
        .log-section.active { display: block; }
        .log-line { margin: 4px 0; white-space: pre-wrap; word-break: break-all; }
        .result-section {
            padding: 20px;
            background: #ecfdf5;
            border-top: 3px solid #10b981;
            display: none;
        }
        .result-section.active { display: block; }
        .result-section h3 { color: #059669; margin-bottom: 10px; }
        .ticket-info { background: white; padding: 15px; border-radius: 8px; }
        .ticket-info p { margin: 8px 0; color: #374151; }
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }
        .status-running { background: #fef3c7; color: #d97706; }
        .status-success { background: #d1fae5; color: #059669; }
        .status-error { background: #fee2e2; color: #dc2626; }
        @media (max-width: 600px) {
            .form-row { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>THSRC Ticket Bot</h1>
            <p>Taiwan High Speed Rail Automated Booking</p>
        </div>

        <form id="bookingForm" class="form-section">
            <div class="form-row">
                <div class="form-group">
                    <label>Start Station</label>
                    <select name="start_station" required>
                        <option value="Nangang">南港 Nangang</option>
                        <option value="Taipei" selected>台北 Taipei</option>
                        <option value="Banqiao">板橋 Banqiao</option>
                        <option value="Taoyuan">桃園 Taoyuan</option>
                        <option value="Hsinchu">新竹 Hsinchu</option>
                        <option value="Miaoli">苗栗 Miaoli</option>
                        <option value="Taichung">台中 Taichung</option>
                        <option value="Changhua">彰化 Changhua</option>
                        <option value="Yunlin">雲林 Yunlin</option>
                        <option value="Chiayi">嘉義 Chiayi</option>
                        <option value="Tainan">台南 Tainan</option>
                        <option value="Zuouing">左營 Zuoying</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Destination Station</label>
                    <select name="dest_station" required>
                        <option value="Nangang">南港 Nangang</option>
                        <option value="Taipei">台北 Taipei</option>
                        <option value="Banqiao">板橋 Banqiao</option>
                        <option value="Taoyuan">桃園 Taoyuan</option>
                        <option value="Hsinchu">新竹 Hsinchu</option>
                        <option value="Miaoli">苗栗 Miaoli</option>
                        <option value="Taichung">台中 Taichung</option>
                        <option value="Changhua">彰化 Changhua</option>
                        <option value="Yunlin">雲林 Yunlin</option>
                        <option value="Chiayi">嘉義 Chiayi</option>
                        <option value="Tainan">台南 Tainan</option>
                        <option value="Zuouing" selected>左營 Zuoying</option>
                    </select>
                </div>
            </div>

            <div class="form-row">
                <div class="form-group">
                    <label>Outbound Date</label>
                    <input type="date" name="outbound_date" required>
                </div>
                <div class="form-group">
                    <label>Outbound Time</label>
                    <input type="time" name="outbound_time" value="12:00" required>
                </div>
            </div>

            <div class="form-row">
                <div class="form-group">
                    <label>ID Number (ROC ID)</label>
                    <input type="text" name="id" placeholder="A123456789" required>
                </div>
                <div class="form-group">
                    <label>Phone Number</label>
                    <input type="tel" name="phone" placeholder="0912345678" required>
                </div>
            </div>

            <div class="form-group">
                <label>Email</label>
                <input type="email" name="email" placeholder="your@email.com" required>
            </div>

            <div class="form-row">
                <div class="form-group">
                    <label>Adult Tickets</label>
                    <input type="number" name="adult" value="1" min="0" max="10">
                </div>
                <div class="form-group">
                    <label>Elder Tickets (65+)</label>
                    <input type="number" name="elder" value="0" min="0" max="10">
                </div>
            </div>

            <div class="form-group">
                <label>TGO Member ID (Optional)</label>
                <input type="text" name="tgo_id" placeholder="Leave empty if not a member">
            </div>

            <div class="form-row">
                <div class="form-group">
                    <label>Auto Retry (Max Attempts)</label>
                    <input type="number" name="max_attempts" value="50" min="1" max="100">
                </div>
                <div class="form-group">
                    <label>Retry Interval (seconds)</label>
                    <input type="number" name="retry_interval" value="5" min="1" max="60">
                </div>
            </div>

            <div class="form-group" style="display: flex; gap: 10px;">
                <button type="submit" class="btn btn-primary" id="submitBtn" style="flex: 1;">Start Auto Booking</button>
                <button type="button" class="btn" id="stopBtn" style="background: #dc2626; color: white; display: none;">Stop</button>
            </div>
        </form>

        <div class="status-bar" id="statusBar" style="display: none; padding: 15px 30px; background: #fef3c7; border-bottom: 2px solid #f59e0b;">
            <span id="attemptCounter" style="font-weight: 600; color: #92400e;"></span>
            <span id="geminiStatus" style="float: right; font-size: 12px;"></span>
        </div>

        <div class="log-section" id="logSection">
            <div id="logContent"></div>
        </div>

        <div class="result-section" id="resultSection">
            <h3>Booking Result</h3>
            <div class="ticket-info" id="ticketInfo"></div>
        </div>
    </div>

    <script>
        // Set default date to tomorrow
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        document.querySelector('input[name="outbound_date"]').value = tomorrow.toISOString().split('T')[0];

        const form = document.getElementById('bookingForm');
        const submitBtn = document.getElementById('submitBtn');
        const stopBtn = document.getElementById('stopBtn');
        const logSection = document.getElementById('logSection');
        const logContent = document.getElementById('logContent');
        const resultSection = document.getElementById('resultSection');
        const ticketInfo = document.getElementById('ticketInfo');
        const statusBar = document.getElementById('statusBar');
        const attemptCounter = document.getElementById('attemptCounter');
        const geminiStatus = document.getElementById('geminiStatus');

        let pollInterval = null;

        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const formData = new FormData(form);
            const data = Object.fromEntries(formData);

            submitBtn.disabled = true;
            submitBtn.textContent = 'Booking in progress...';
            stopBtn.style.display = 'block';
            statusBar.style.display = 'block';
            logSection.classList.add('active');
            resultSection.classList.remove('active');
            logContent.innerHTML = '';

            try {
                const response = await fetch('/api/book', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                if (response.ok) {
                    startPolling();
                } else {
                    const error = await response.json();
                    logContent.innerHTML += `<div class="log-line" style="color:#ef4444">Error: ${error.message}</div>`;
                    resetUI();
                }
            } catch (err) {
                logContent.innerHTML += `<div class="log-line" style="color:#ef4444">Network error: ${err.message}</div>`;
                resetUI();
            }
        });

        stopBtn.addEventListener('click', async () => {
            try {
                await fetch('/api/stop', { method: 'POST' });
                stopBtn.textContent = 'Stopping...';
                stopBtn.disabled = true;
            } catch (err) {
                console.error('Stop error:', err);
            }
        });

        function resetUI() {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Start Auto Booking';
            stopBtn.style.display = 'none';
            stopBtn.textContent = 'Stop';
            stopBtn.disabled = false;
            statusBar.style.display = 'none';
        }

        function startPolling() {
            pollInterval = setInterval(async () => {
                try {
                    const response = await fetch('/api/status');
                    const status = await response.json();

                    // Update attempt counter
                    attemptCounter.textContent = `Attempt: ${status.attempt} / ${status.max_attempts}`;
                    geminiStatus.innerHTML = status.gemini_enabled
                        ? '<span style="color:#059669;">Gemini Vision: ON</span>'
                        : '<span style="color:#9ca3af;">Gemini Vision: OFF</span>';

                    // Update logs
                    logContent.innerHTML = status.logs.map(log =>
                        `<div class="log-line">${log}</div>`
                    ).join('');
                    logSection.scrollTop = logSection.scrollHeight;

                    // Check if done
                    if (!status.running) {
                        clearInterval(pollInterval);
                        resetUI();

                        if (status.result) {
                            resultSection.classList.add('active');
                            ticketInfo.innerHTML = `<p><strong>Reservation No:</strong> ${status.result}</p>`;
                        }
                    }
                } catch (err) {
                    console.error('Polling error:', err);
                }
            }, 1000);
        }
    </script>
</body>
</html>
'''

LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - THSRC Ticket Bot</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-box {
            background: white;
            padding: 40px;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            width: 100%;
            max-width: 400px;
        }
        h1 { text-align: center; margin-bottom: 30px; color: #374151; }
        input {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e5e7eb;
            border-radius: 8px;
            font-size: 16px;
            margin-bottom: 20px;
        }
        button {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
        }
        .error { color: #dc2626; text-align: center; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="login-box">
        <h1>THSRC Ticket Bot</h1>
        {% if error %}<p class="error">{{ error }}</p>{% endif %}
        <form method="POST">
            <input type="password" name="password" placeholder="Enter password" required>
            <button type="submit">Login</button>
        </form>
    </div>
</body>
</html>
'''


def check_auth(f):
    """Decorator to check authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if APP_PASSWORD:
            auth = request.cookies.get('auth')
            if auth != APP_PASSWORD:
                return render_template_string(LOGIN_TEMPLATE, error=None), 401
        return f(*args, **kwargs)
    return decorated


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == APP_PASSWORD:
            response = app.make_response(render_template_string(HTML_TEMPLATE))
            response.set_cookie('auth', APP_PASSWORD, httponly=True, samesite='Lax')
            return response
        return render_template_string(LOGIN_TEMPLATE, error='Incorrect password')
    return render_template_string(LOGIN_TEMPLATE, error=None)


@app.route('/')
@check_auth
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})


@app.route('/api/book', methods=['POST'])
@check_auth
def start_booking():
    global booking_status

    if booking_status['running']:
        return jsonify({'error': True, 'message': 'Booking already in progress'}), 400

    data = request.json

    # Reset status
    booking_status['running'] = True
    booking_status['logs'] = []
    booking_status['result'] = None

    # Start booking in background thread
    thread = threading.Thread(target=run_booking, args=(data,))
    thread.daemon = True
    thread.start()
    booking_status['thread'] = thread

    return jsonify({'success': True, 'message': 'Booking started'})


@app.route('/api/status')
@check_auth
def get_status():
    return jsonify({
        'running': booking_status['running'],
        'logs': booking_status['logs'][-100:],  # Last 100 lines
        'result': booking_status['result'],
        'attempt': booking_status['attempt'],
        'max_attempts': booking_status['max_attempts'],
        'gemini_enabled': bool(GEMINI_API_KEY)
    })


@app.route('/api/stop', methods=['POST'])
@check_auth
def stop_booking():
    global booking_status
    booking_status['stop_requested'] = True
    return jsonify({'success': True, 'message': 'Stop requested'})


class WebLogHandler(logging.Handler):
    """Custom log handler to capture logs for web interface"""
    def emit(self, record):
        try:
            msg = self.format(record)
            booking_status['logs'].append(msg)
        except Exception:
            pass


def run_booking(data):
    """Run the booking process in background with auto-retry"""
    global booking_status
    import time as time_module

    # Setup logging
    logger = logging.getLogger('THSRC')
    logger.setLevel(logging.INFO)
    handler = WebLogHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', '%H:%M:%S'))
    logger.addHandler(handler)

    max_attempts = int(data.get('max_attempts', 50))
    retry_interval = int(data.get('retry_interval', 5))
    booking_status['max_attempts'] = max_attempts

    # Log OCR system status
    if GEMINI_API_KEY:
        logger.info("Dual OCR System: holey.cc + Gemini Vision (ENABLED)")
    else:
        logger.info("OCR System: holey.cc only (Set GEMINI_API_KEY for better accuracy)")

    try:
        # Update user_config.toml with form data
        import rtoml
        from pathlib import Path

        config_path = Path(__file__).parent / 'user_config.toml'
        config = rtoml.load(config_path)

        # Update fields
        config['fields']['THSRC']['id'] = data.get('id', '')
        config['fields']['THSRC']['start-station'] = data.get('start_station', 'Taipei')
        config['fields']['THSRC']['dest-station'] = data.get('dest_station', 'Zuouing')
        config['fields']['THSRC']['outbound-date'] = data.get('outbound_date', '')
        config['fields']['THSRC']['outbound-time'] = data.get('outbound_time', '12:00')
        config['fields']['THSRC']['phone'] = data.get('phone', '')
        config['fields']['THSRC']['email'] = data.get('email', '')
        config['fields']['THSRC']['tgo-id'] = data.get('tgo_id', '')
        config['fields']['THSRC']['ticket']['adult'] = int(data.get('adult', 1))
        config['fields']['THSRC']['ticket']['elder'] = int(data.get('elder', 0))

        # Save config
        rtoml.dump(config, config_path)

        logger.info(f"Booking: {data.get('start_station')} -> {data.get('dest_station')}")
        logger.info(f"Date: {data.get('outbound_date')} {data.get('outbound_time')}")
        logger.info(f"Auto-retry enabled: Max {max_attempts} attempts, {retry_interval}s interval")

        # Import booking modules
        from services.thsrc import THSRC
        from utils.io import load_toml
        from configs.config import filenames

        class Args:
            def __init__(self):
                self.log = logger
                self.config = load_toml(str(filenames.config).format(service='THSRC'))
                self.service = 'THSRC'
                self.locale = 'zh-TW'
                self.auto = True
                self.list = False
                self.proxy = None

        # Auto-retry loop
        for attempt in range(1, max_attempts + 1):
            if booking_status['stop_requested']:
                logger.info("Booking stopped by user")
                break

            booking_status['attempt'] = attempt
            logger.info(f"\n{'='*50}")
            logger.info(f"AUTO-RETRY ATTEMPT {attempt}/{max_attempts}")
            logger.info(f"{'='*50}")

            try:
                args = Args()
                thsrc = THSRC(args)
                thsrc.main()

                # If we get here without exception, booking was successful
                logger.info("Booking completed successfully!")
                booking_status['result'] = 'SUCCESS'
                break

            except SystemExit as e:
                if e.code == 0:
                    logger.info("Booking completed successfully!")
                    booking_status['result'] = 'SUCCESS'
                    break
                else:
                    logger.warning(f"Attempt {attempt} failed (exit code: {e.code})")
                    if attempt < max_attempts and not booking_status['stop_requested']:
                        logger.info(f"Waiting {retry_interval}s before next attempt...")
                        time_module.sleep(retry_interval)

            except Exception as e:
                logger.warning(f"Attempt {attempt} error: {str(e)}")
                if attempt < max_attempts and not booking_status['stop_requested']:
                    logger.info(f"Waiting {retry_interval}s before next attempt...")
                    time_module.sleep(retry_interval)

        else:
            logger.error(f"All {max_attempts} attempts failed. Please try again later.")

    except Exception as e:
        logger.error(f"Booking error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        booking_status['running'] = False
        booking_status['stop_requested'] = False
        booking_status['attempt'] = 0
        logger.removeHandler(handler)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'

    print(f"\n{'='*60}")
    print("THSRC Ticket Bot - Web/Docker Version")
    print(f"{'='*60}")
    print(f"Server: http://localhost:{port}")
    print(f"Password protection: {'ENABLED' if APP_PASSWORD else 'DISABLED'}")
    print(f"Gemini Vision OCR: {'ENABLED' if GEMINI_API_KEY else 'DISABLED (set GEMINI_API_KEY)'}")
    print(f"{'='*60}\n")

    app.run(host='0.0.0.0', port=port, debug=debug)
