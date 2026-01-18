# THSRC Ticket Bot - Web/Docker Version

## Project Overview

This is the **Web/Docker version** of the THSRC (Taiwan High Speed Rail) ticket booking bot, designed for deployment on Zeabur or other cloud platforms.

**Key difference from local version:** This version uses **Selenium + Chrome** for browser automation instead of httpx.

## Architecture

```
webticketbot/
├── web_app.py          # Flask web interface (main entry for Docker)
├── ticket_bot.py       # CLI entry point
├── Dockerfile          # Docker configuration with Chrome
├── requirements.txt    # Python dependencies (includes selenium)
├── zeabur.json         # Zeabur deployment config
├── user_config.toml    # User configuration
├── constants.py        # Service constants
├── services/
│   ├── base_service.py # Selenium WebDriver initialization
│   └── thsrc.py        # THSRC booking logic (Selenium version)
├── configs/
│   ├── config.py       # App configuration
│   └── THSRC.toml      # THSRC service config
└── utils/
    ├── validate.py     # ID validation
    ├── proxy.py        # Proxy utilities
    ├── io.py           # File I/O utilities
    └── captcha_ocr.py  # Dual OCR (holey.cc + Gemini Vision)
```

## Key Components

### base_service.py (Selenium)
- Initializes Chrome WebDriver with headless mode
- Docker-specific options: `--no-sandbox`, `--no-zygote`, `--single-process`
- Auto-detects Chrome binary via `CHROME_BIN` env var
- Uses webdriver-manager for ChromeDriver

### thsrc.py (Selenium)
- Uses WebDriver to interact with THSRC website
- Form filling via Selenium element interactions
- **Dual Captcha OCR: holey.cc + Gemini Vision** for higher accuracy
- Full booking flow: search → select train → confirm → result

### utils/captcha_ocr.py (NEW)
- Dual OCR system combining holey.cc API and Google Gemini Vision
- Automatic fallback: tries holey.cc first, falls back to Gemini if failed
- Supports retry mechanism for higher accuracy

### web_app.py (Flask)
- Web interface for booking
- Password protection via `APP_PASSWORD` env var
- Real-time log streaming
- Background booking thread
- **Auto-retry mechanism** with configurable max attempts (default: 50)
- **Stop button** to cancel ongoing booking
- Displays Gemini Vision OCR status

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `APP_PASSWORD` | Web interface password | Yes (for security) |
| `GEMINI_API_KEY` | Google Gemini API key for Vision OCR | Recommended (improves accuracy) |
| `CHROME_BIN` | Chrome binary path | No (auto-detected) |
| `CHROMEDRIVER_PATH` | ChromeDriver path | No (auto-downloaded) |
| `PORT` | Web server port | No (default: 8080) |
| `DOCKER_ENV` | Set to "1" in Docker | Auto-set in Dockerfile |

## Development Commands

```bash
# Local test (requires Chrome installed)
export GEMINI_API_KEY=your_gemini_api_key  # Optional but recommended
python web_app.py

# Docker build and run
docker build -t webticketbot .
docker run -e APP_PASSWORD=yourpassword -e GEMINI_API_KEY=your_key -p 8080:8080 webticketbot

# CLI mode
python ticket_bot.py thsrc -a
```

## Deployment (Zeabur)

1. Push to GitHub repository
2. Connect repo to Zeabur
3. Set environment variables:
   - `APP_PASSWORD` (required)
   - `GEMINI_API_KEY` (recommended for better captcha OCR)
4. Deploy

## Related Project

**Local CLI version:** `/Users/zino/Desktop/OpenAI/Ticket-Bot-main/`
- Uses httpx (no browser)
- Simpler, faster for local use
- Do NOT mix code between versions
