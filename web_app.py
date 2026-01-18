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

# HTML Template (TrainFlow Service Theme)
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TrainFlow 列車流 - 高鐵自動訂票系統</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Nunito+Sans:wght@300;400;500;600;700&family=Varela+Round&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #10B981;
            --primary-light: #34D399;
            --secondary: #8B5CF6;
            --background: #FDF8F5;
            --background-card: rgba(255, 255, 255, 0.85);
            --text-primary: #064E3B;
            --text-secondary: #475569;
            --text-muted: #94A3B8;
            --accent-pink: #FECDD3;
            --accent-sage: #D1FAE5;
            --accent-cream: #FEF3C7;
            --accent-gold: #D4AF37;
            --border: rgba(16, 185, 129, 0.15);
            --shadow-soft: 0 4px 20px rgba(16, 185, 129, 0.08);
            --shadow-medium: 0 8px 30px rgba(16, 185, 129, 0.12);
            --shadow-glow: 0 0 40px rgba(139, 92, 246, 0.15);
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        html { scroll-behavior: smooth; }
        body {
            font-family: 'Nunito Sans', -apple-system, BlinkMacSystemFont, 'Microsoft JhengHei', sans-serif;
            background: var(--background);
            background-image:
                radial-gradient(ellipse at 20% 20%, rgba(254, 205, 211, 0.3) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 80%, rgba(209, 250, 229, 0.3) 0%, transparent 50%),
                radial-gradient(ellipse at 50% 50%, rgba(139, 92, 246, 0.05) 0%, transparent 70%);
            min-height: 100vh;
            color: var(--text-primary);
            line-height: 1.6;
        }
        h1, h2, h3, h4 { font-family: 'Varela Round', sans-serif; }

        /* Navigation */
        .navbar {
            position: fixed;
            top: 16px;
            left: 16px;
            right: 16px;
            background: var(--background-card);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-radius: 16px;
            padding: 16px 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            z-index: 1000;
            box-shadow: var(--shadow-soft);
            border: 1px solid var(--border);
        }
        .logo {
            font-family: 'Varela Round', sans-serif;
            font-size: 24px;
            color: var(--primary);
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .logo-icon {
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .logo-icon svg { width: 24px; height: 24px; color: white; }
        .nav-links { display: flex; gap: 32px; }
        .nav-links a {
            color: var(--text-secondary);
            text-decoration: none;
            font-weight: 500;
            transition: color 0.2s;
            cursor: pointer;
        }
        .nav-links a:hover { color: var(--primary); }

        /* Hero Section */
        .hero {
            padding: 140px 24px 80px;
            text-align: center;
            max-width: 900px;
            margin: 0 auto;
        }
        .hero-badge {
            display: inline-block;
            background: var(--accent-sage);
            color: var(--primary);
            padding: 8px 20px;
            border-radius: 50px;
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 24px;
        }
        .hero h1 {
            font-size: clamp(36px, 6vw, 56px);
            color: var(--text-primary);
            margin-bottom: 20px;
            line-height: 1.2;
        }
        .hero h1 span { color: var(--secondary); }
        .hero p {
            font-size: 18px;
            color: var(--text-secondary);
            max-width: 600px;
            margin: 0 auto 40px;
        }
        .hero-cta {
            display: flex;
            gap: 16px;
            justify-content: center;
            flex-wrap: wrap;
        }
        .btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 16px 32px;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            text-decoration: none;
        }
        .btn-primary {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
            color: white;
            box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3);
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(16, 185, 129, 0.4);
        }
        .btn-secondary {
            background: var(--background-card);
            color: var(--text-primary);
            border: 2px solid var(--border);
        }
        .btn-secondary:hover {
            border-color: var(--primary);
            background: rgba(16, 185, 129, 0.05);
        }
        .btn:disabled {
            background: var(--text-muted);
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }

        /* Services Section */
        .section {
            padding: 80px 24px;
            max-width: 1200px;
            margin: 0 auto;
        }
        .section-header {
            text-align: center;
            margin-bottom: 60px;
        }
        .section-header h2 {
            font-size: 36px;
            margin-bottom: 16px;
            color: var(--text-primary);
        }
        .section-header p {
            color: var(--text-secondary);
            max-width: 500px;
            margin: 0 auto;
        }
        .services-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 24px;
        }
        .service-card {
            background: var(--background-card);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 32px;
            border: 1px solid var(--border);
            box-shadow: var(--shadow-soft);
            transition: all 0.3s ease;
            cursor: pointer;
        }
        .service-card:hover {
            transform: translateY(-5px);
            box-shadow: var(--shadow-medium);
        }
        .service-icon {
            width: 60px;
            height: 60px;
            border-radius: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 20px;
        }
        .service-icon.pink { background: var(--accent-pink); }
        .service-icon.sage { background: var(--accent-sage); }
        .service-icon.cream { background: var(--accent-cream); }
        .service-icon svg { width: 28px; height: 28px; }
        .service-card h3 {
            font-size: 20px;
            margin-bottom: 12px;
            color: var(--text-primary);
        }
        .service-card p {
            color: var(--text-secondary);
            font-size: 15px;
        }

        /* Gallery Section */
        .gallery-section {
            background: linear-gradient(180deg, transparent 0%, rgba(209, 250, 229, 0.2) 50%, transparent 100%);
        }
        .gallery-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 24px;
        }
        .gallery-item {
            position: relative;
            border-radius: 20px;
            overflow: hidden;
            aspect-ratio: 4/3;
            background: linear-gradient(135deg, var(--accent-pink) 0%, var(--accent-sage) 100%);
            cursor: pointer;
            transition: transform 0.3s ease;
        }
        .gallery-item:hover { transform: scale(1.02); }
        .gallery-item::after {
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(to top, rgba(0,0,0,0.4) 0%, transparent 50%);
        }
        .gallery-label {
            position: absolute;
            bottom: 16px;
            left: 16px;
            right: 16px;
            z-index: 1;
            color: white;
            font-weight: 600;
        }
        .gallery-label span {
            display: block;
            font-size: 12px;
            opacity: 0.8;
            margin-bottom: 4px;
        }
        @media (max-width: 768px) {
            .gallery-grid { grid-template-columns: 1fr; }
        }

        /* Booking Section */
        .booking-section {
            background: linear-gradient(180deg, transparent 0%, rgba(254, 205, 211, 0.15) 100%);
        }
        .booking-container {
            background: var(--background-card);
            backdrop-filter: blur(20px);
            border-radius: 24px;
            padding: 48px;
            border: 1px solid var(--border);
            box-shadow: var(--shadow-medium);
            max-width: 900px;
            margin: 0 auto;
        }
        .booking-header {
            text-align: center;
            margin-bottom: 40px;
        }
        .booking-header h2 {
            font-size: 32px;
            margin-bottom: 12px;
        }
        .form-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-group.full-width { grid-column: 1 / -1; }
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: var(--text-primary);
            font-size: 14px;
        }
        .form-group input,
        .form-group select {
            width: 100%;
            padding: 14px 18px;
            border: 2px solid var(--border);
            border-radius: 12px;
            font-size: 16px;
            font-family: inherit;
            background: white;
            color: var(--text-primary);
            transition: all 0.2s ease;
        }
        .form-group input:focus,
        .form-group select:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.1);
        }
        .form-group input::placeholder { color: var(--text-muted); }

        /* Settings Panel */
        .settings-panel {
            background: rgba(139, 92, 246, 0.05);
            border: 1px solid rgba(139, 92, 246, 0.15);
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 32px;
        }
        .settings-toggle {
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
        }
        .settings-toggle span:first-child {
            font-weight: 600;
            color: var(--secondary);
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .settings-content {
            display: none;
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid rgba(139, 92, 246, 0.15);
        }
        .settings-content.active { display: block; }
        .info-box {
            background: white;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
            border: 1px solid var(--border);
        }
        .info-box p { font-size: 13px; color: var(--text-secondary); margin: 8px 0; }
        .info-box strong { color: var(--text-primary); }
        .privacy-notice {
            background: var(--accent-cream);
            border-radius: 10px;
            padding: 12px 16px;
            font-size: 12px;
            color: #92400E;
            margin-top: 12px;
        }

        /* Status Bar */
        .status-bar {
            display: none;
            background: var(--accent-cream);
            border-radius: 12px;
            padding: 16px 20px;
            margin-bottom: 20px;
            border: 1px solid rgba(212, 175, 55, 0.3);
        }
        .status-bar.active { display: flex; justify-content: space-between; align-items: center; }

        /* Log Section */
        .log-section {
            display: none;
            background: #1E293B;
            border-radius: 16px;
            padding: 20px;
            margin-top: 24px;
            max-height: 350px;
            overflow-y: auto;
        }
        .log-section.active { display: block; }
        .log-content {
            font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
            font-size: 13px;
            color: var(--primary-light);
            line-height: 1.8;
        }
        .log-line { margin: 4px 0; white-space: pre-wrap; word-break: break-all; }

        /* Result Section */
        .result-section {
            display: none;
            background: var(--accent-sage);
            border-radius: 16px;
            padding: 24px;
            margin-top: 24px;
            border: 2px solid var(--primary);
        }
        .result-section.active { display: block; }
        .result-section h3 {
            color: var(--primary);
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .ticket-info {
            background: white;
            border-radius: 12px;
            padding: 20px;
        }
        .ticket-info p { margin: 8px 0; color: var(--text-primary); }

        /* Testimonials */
        .testimonials-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 24px;
        }
        .testimonial-card {
            background: var(--background-card);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 32px;
            border: 1px solid var(--border);
            box-shadow: var(--shadow-soft);
        }
        .testimonial-text {
            font-size: 16px;
            color: var(--text-secondary);
            font-style: italic;
            margin-bottom: 24px;
            line-height: 1.8;
        }
        .testimonial-author {
            display: flex;
            align-items: center;
            gap: 16px;
        }
        .testimonial-avatar {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: linear-gradient(135deg, var(--accent-pink), var(--accent-sage));
        }
        .testimonial-name {
            font-weight: 700;
            color: var(--text-primary);
        }
        .testimonial-role {
            font-size: 13px;
            color: var(--text-muted);
        }
        .testimonial-stars {
            color: var(--accent-gold);
            margin-bottom: 16px;
            letter-spacing: 2px;
        }

        /* Footer */
        .footer {
            background: var(--text-primary);
            color: white;
            padding: 60px 24px 30px;
            margin-top: 80px;
        }
        .footer-content {
            max-width: 1200px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 40px;
        }
        .footer h4 {
            font-size: 18px;
            margin-bottom: 20px;
            color: var(--primary-light);
        }
        .footer p, .footer a {
            color: rgba(255,255,255,0.7);
            font-size: 14px;
            line-height: 2;
            text-decoration: none;
        }
        .footer a:hover { color: white; }
        .footer-bottom {
            max-width: 1200px;
            margin: 40px auto 0;
            padding-top: 30px;
            border-top: 1px solid rgba(255,255,255,0.1);
            text-align: center;
            color: rgba(255,255,255,0.5);
            font-size: 13px;
        }

        /* Responsive */
        @media (max-width: 768px) {
            .navbar { padding: 12px 20px; }
            .nav-links { display: none; }
            .form-grid { grid-template-columns: 1fr; }
            .booking-container { padding: 24px; }
            .hero { padding: 120px 20px 60px; }
        }

        /* Animations */
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-in { animation: fadeIn 0.6s ease-out forwards; }
    </style>
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar">
        <div class="logo">
            <div class="logo-icon">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
            </div>
            TrainFlow
        </div>
        <div class="nav-links">
            <a onclick="scrollToSection('services')">服務項目</a>
            <a onclick="scrollToSection('gallery')">操作說明</a>
            <a onclick="scrollToSection('booking')">立即預約</a>
            <a onclick="scrollToSection('testimonials')">顧客評價</a>
        </div>
    </nav>

    <!-- Hero Section -->
    <section class="hero animate-fade-in">
        <div class="hero-badge">高鐵自動訂票系統</div>
        <h1>順暢無阻的<span>訂票體驗</span></h1>
        <p>結合先進的自動化技術，讓您如流水般順暢地完成高鐵訂票。智慧驗證、自動重試，為您打造極致的訂票流程。</p>
        <div class="hero-cta">
            <a href="#booking" class="btn btn-primary" onclick="scrollToSection('booking')">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                立即預約
            </a>
            <a href="#services" class="btn btn-secondary" onclick="scrollToSection('services')">
                了解更多
            </a>
        </div>
    </section>

    <!-- Services Section -->
    <section id="services" class="section">
        <div class="section-header">
            <h2>專屬服務</h2>
            <p>我們提供多元化的訂票服務，滿足您的各種需求</p>
        </div>
        <div class="services-grid">
            <div class="service-card">
                <div class="service-icon pink">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="#BE185D">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                </div>
                <h3>極速訂票</h3>
                <p>採用 Selenium 自動化技術，快速填寫表單並完成訂票，省去繁瑣的手動操作。</p>
            </div>
            <div class="service-card">
                <div class="service-icon sage">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="#059669">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                    </svg>
                </div>
                <h3>智慧驗證</h3>
                <p>結合 holey.cc 與 Gemini Vision 雙重 OCR 辨識，大幅提升驗證碼識別準確率。</p>
            </div>
            <div class="service-card">
                <div class="service-icon cream">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="#D97706">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                </div>
                <h3>自動重試</h3>
                <p>訂票失敗時自動重新嘗試，最高可設定 100 次重試，持續為您搶票直到成功。</p>
            </div>
        </div>
    </section>

    <!-- Gallery Section -->
    <section id="gallery" class="section gallery-section">
        <div class="section-header">
            <h2>操作說明</h2>
            <p>三步驟完成訂票，簡單又快速</p>
        </div>
        <div class="gallery-grid">
            <div class="gallery-item">
                <div class="gallery-label">
                    <span>Step 1</span>
                    填寫訂票資訊
                </div>
            </div>
            <div class="gallery-item">
                <div class="gallery-label">
                    <span>Step 2</span>
                    自動驗證處理
                </div>
            </div>
            <div class="gallery-item">
                <div class="gallery-label">
                    <span>Step 3</span>
                    成功取得車票
                </div>
            </div>
        </div>
    </section>

    <!-- Booking Section -->
    <section id="booking" class="section booking-section">
        <div class="booking-container">
            <div class="booking-header">
                <h2>預約您的旅程</h2>
                <p style="color: var(--text-secondary);">填寫以下資訊，開始自動訂票</p>
            </div>

            <!-- Settings Panel -->
            <div class="settings-panel">
                <div class="settings-toggle" onclick="toggleSettings()">
                    <span>
                        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        </svg>
                        驗證碼辨識設定
                    </span>
                    <span id="settingsToggle" style="color: var(--text-muted); font-size: 14px;">展開</span>
                </div>
                <div id="settingsContent" class="settings-content">
                    <div class="info-box">
                        <p><strong style="color: var(--secondary);">辨識模式說明：</strong></p>
                        <p>未設定 Gemini API Key → 使用 holey.cc 單一辨識服務</p>
                        <p>已設定 Gemini API Key → holey.cc + Gemini Vision 雙重辨識，準確率更高</p>
                    </div>
                    <div class="form-group">
                        <label>
                            Gemini API Key (選填)
                            <a href="https://aistudio.google.com/app/apikey" target="_blank" style="font-size: 12px; color: var(--secondary); margin-left: 10px;">免費取得 API Key →</a>
                        </label>
                        <div style="display: flex; gap: 12px;">
                            <input type="password" id="geminiApiKey" placeholder="輸入您的 Gemini API Key (可選)" style="flex: 1;">
                            <button type="button" onclick="verifyGeminiKey()" class="btn btn-secondary" style="padding: 14px 24px;">驗證</button>
                        </div>
                        <span id="geminiKeyStatus" style="display: block; margin-top: 8px; font-size: 13px;"></span>
                    </div>
                    <div class="privacy-notice">
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" style="display: inline; vertical-align: middle; margin-right: 4px;">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                        </svg>
                        <strong>隱私保護聲明：</strong>您的 API Key 僅儲存於本機設定檔中，不會上傳至雲端伺服器。
                    </div>
                </div>
            </div>

            <!-- Booking Form -->
            <form id="bookingForm">
                <div class="form-grid">
                    <div class="form-group">
                        <label>出發站</label>
                        <select name="start_station" required>
                            <option value="Nangang">南港</option>
                            <option value="Taipei" selected>台北</option>
                            <option value="Banqiao">板橋</option>
                            <option value="Taoyuan">桃園</option>
                            <option value="Hsinchu">新竹</option>
                            <option value="Miaoli">苗栗</option>
                            <option value="Taichung">台中</option>
                            <option value="Changhua">彰化</option>
                            <option value="Yunlin">雲林</option>
                            <option value="Chiayi">嘉義</option>
                            <option value="Tainan">台南</option>
                            <option value="Zuouing">左營</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>抵達站</label>
                        <select name="dest_station" required>
                            <option value="Nangang">南港</option>
                            <option value="Taipei">台北</option>
                            <option value="Banqiao">板橋</option>
                            <option value="Taoyuan">桃園</option>
                            <option value="Hsinchu">新竹</option>
                            <option value="Miaoli">苗栗</option>
                            <option value="Taichung">台中</option>
                            <option value="Changhua">彰化</option>
                            <option value="Yunlin">雲林</option>
                            <option value="Chiayi">嘉義</option>
                            <option value="Tainan">台南</option>
                            <option value="Zuouing" selected>左營</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>出發日期</label>
                        <input type="date" name="outbound_date" required>
                    </div>
                    <div class="form-group">
                        <label>出發時間</label>
                        <input type="time" name="outbound_time" value="12:00" required>
                    </div>
                    <div class="form-group">
                        <label>身分證字號</label>
                        <input type="text" name="id" placeholder="A123456789" required>
                    </div>
                    <div class="form-group">
                        <label>手機號碼</label>
                        <input type="tel" name="phone" placeholder="0912345678" required>
                    </div>
                    <div class="form-group full-width">
                        <label>電子郵件</label>
                        <input type="email" name="email" placeholder="your@email.com" required>
                    </div>
                    <div class="form-group">
                        <label>全票張數</label>
                        <input type="number" name="adult" value="1" min="0" max="10">
                    </div>
                    <div class="form-group">
                        <label>愛心票張數</label>
                        <input type="number" name="disabled" value="0" min="0" max="10">
                    </div>
                    <div class="form-group full-width" id="disabledIdsGroup" style="display: none;">
                        <label>愛心票乘客身分證字號 (多人請用逗號分隔)</label>
                        <input type="text" name="disabled_ids" placeholder="A123456789, B234567890">
                    </div>
                    <div class="form-group">
                        <label>敬老票張數 (65歲以上)</label>
                        <input type="number" name="elder" value="0" min="0" max="10">
                    </div>
                    <div class="form-group">
                        <label>TGO 會員編號 (選填)</label>
                        <input type="text" name="tgo_id" placeholder="非會員請留空">
                    </div>
                    <div class="form-group full-width" id="elderIdsGroup" style="display: none;">
                        <label>敬老票乘客身分證字號 (多人請用逗號分隔)</label>
                        <input type="text" name="elder_ids" placeholder="A123456789, B234567890">
                    </div>
                    <div class="form-group">
                        <label>最大重試次數</label>
                        <input type="number" name="max_attempts" value="50" min="1" max="100">
                    </div>
                    <div class="form-group">
                        <label>重試間隔 (秒)</label>
                        <input type="number" name="retry_interval" value="5" min="1" max="60">
                    </div>
                </div>

                <div style="display: flex; gap: 16px; margin-top: 32px;">
                    <button type="submit" class="btn btn-primary" id="submitBtn" style="flex: 1;">
                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                        開始自動訂票
                    </button>
                    <button type="button" class="btn" id="stopBtn" style="background: #EF4444; color: white; display: none; padding: 16px 32px;">
                        停止
                    </button>
                </div>
            </form>

            <!-- Status Bar -->
            <div class="status-bar" id="statusBar">
                <span id="attemptCounter" style="font-weight: 600; color: #92400E;"></span>
                <span id="geminiStatus" style="font-size: 13px;"></span>
            </div>

            <!-- Log Section -->
            <div class="log-section" id="logSection">
                <div class="log-content" id="logContent"></div>
            </div>

            <!-- Result Section -->
            <div class="result-section" id="resultSection">
                <h3>
                    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    訂票成功
                </h3>
                <div class="ticket-info" id="ticketInfo"></div>
            </div>
        </div>
    </section>

    <!-- Testimonials Section -->
    <section id="testimonials" class="section">
        <div class="section-header">
            <h2>顧客評價</h2>
            <p>聽聽使用者怎麼說</p>
        </div>
        <div class="testimonials-grid">
            <div class="testimonial-card">
                <div class="testimonial-stars">★★★★★</div>
                <p class="testimonial-text">「自動訂票功能太方便了！以前搶票總是搶不到，現在只要設定好資料，系統就會自動幫我訂票。」</p>
                <div class="testimonial-author">
                    <div class="testimonial-avatar"></div>
                    <div>
                        <div class="testimonial-name">陳小姐</div>
                        <div class="testimonial-role">台北 → 高雄 通勤族</div>
                    </div>
                </div>
            </div>
            <div class="testimonial-card">
                <div class="testimonial-stars">★★★★★</div>
                <p class="testimonial-text">「Gemini 驗證碼辨識功能大幅提升了成功率，以前常因為驗證碼錯誤而失敗，現在幾乎每次都能成功。」</p>
                <div class="testimonial-author">
                    <div class="testimonial-avatar"></div>
                    <div>
                        <div class="testimonial-name">林先生</div>
                        <div class="testimonial-role">商務旅客</div>
                    </div>
                </div>
            </div>
            <div class="testimonial-card">
                <div class="testimonial-stars">★★★★★</div>
                <p class="testimonial-text">「介面設計很美觀，操作也很直覺。最喜歡自動重試功能，即使第一次沒搶到也會持續嘗試。」</p>
                <div class="testimonial-author">
                    <div class="testimonial-avatar"></div>
                    <div>
                        <div class="testimonial-name">王小姐</div>
                        <div class="testimonial-role">學生</div>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- Footer -->
    <footer class="footer">
        <div class="footer-content">
            <div>
                <h4>TrainFlow 列車流</h4>
                <p>高鐵自動訂票系統<br>讓訂票如流水般順暢</p>
            </div>
            <div>
                <h4>服務項目</h4>
                <a href="#services">極速訂票</a><br>
                <a href="#services">智慧驗證</a><br>
                <a href="#services">自動重試</a>
            </div>
            <div>
                <h4>聯絡我們</h4>
                <p>技術支援：support@example.com</p>
                <p>服務時間：24/7 全天候</p>
            </div>
        </div>
        <div class="footer-bottom">
            © 2025 TrainFlow 列車流 - THSRC Ticket Bot. All rights reserved.
        </div>
    </footer>

    <script>
        // Smooth scroll to section
        function scrollToSection(id) {
            document.getElementById(id).scrollIntoView({ behavior: 'smooth' });
        }

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

        // Dynamic show/hide for disabled/elder ID fields
        const disabledInput = document.querySelector('input[name="disabled"]');
        const elderInput = document.querySelector('input[name="elder"]');
        const disabledIdsGroup = document.getElementById('disabledIdsGroup');
        const elderIdsGroup = document.getElementById('elderIdsGroup');

        disabledInput.addEventListener('change', () => {
            disabledIdsGroup.style.display = parseInt(disabledInput.value) > 0 ? 'block' : 'none';
        });
        elderInput.addEventListener('change', () => {
            elderIdsGroup.style.display = parseInt(elderInput.value) > 0 ? 'block' : 'none';
        });

        let pollInterval = null;

        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const formData = new FormData(form);
            const data = Object.fromEntries(formData);

            submitBtn.disabled = true;
            submitBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" style="animation: spin 1s linear infinite;"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg> 訂票中...';
            stopBtn.style.display = 'block';
            statusBar.classList.add('active');
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
                    logContent.innerHTML += `<div class="log-line" style="color:#EF4444">錯誤: ${error.message}</div>`;
                    resetUI();
                }
            } catch (err) {
                logContent.innerHTML += `<div class="log-line" style="color:#EF4444">網路錯誤: ${err.message}</div>`;
                resetUI();
            }
        });

        stopBtn.addEventListener('click', async () => {
            try {
                await fetch('/api/stop', { method: 'POST' });
                stopBtn.textContent = '停止中...';
                stopBtn.disabled = true;
            } catch (err) {
                console.error('Stop error:', err);
            }
        });

        function resetUI() {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg> 開始自動訂票';
            stopBtn.style.display = 'none';
            stopBtn.textContent = '停止';
            stopBtn.disabled = false;
            statusBar.classList.remove('active');
        }

        function startPolling() {
            pollInterval = setInterval(async () => {
                try {
                    const response = await fetch('/api/status');
                    const status = await response.json();

                    attemptCounter.textContent = `嘗試次數: ${status.attempt} / ${status.max_attempts}`;
                    geminiStatus.innerHTML = status.gemini_enabled
                        ? '<span style="color:#059669;">Gemini 辨識: 開啟</span>'
                        : '<span style="color:#94A3B8;">Gemini 辨識: 關閉</span>';

                    logContent.innerHTML = status.logs.map(log =>
                        `<div class="log-line">${log}</div>`
                    ).join('');
                    logSection.scrollTop = logSection.scrollHeight;

                    if (!status.running) {
                        clearInterval(pollInterval);
                        resetUI();

                        if (status.result) {
                            resultSection.classList.add('active');
                            ticketInfo.innerHTML = `<p><strong>訂位代號:</strong> ${status.result}</p>`;
                        }
                    }
                } catch (err) {
                    console.error('Polling error:', err);
                }
            }, 1000);
        }

        // Settings toggle
        function toggleSettings() {
            const content = document.getElementById('settingsContent');
            const toggle = document.getElementById('settingsToggle');
            if (content.classList.contains('active')) {
                content.classList.remove('active');
                toggle.textContent = '展開';
            } else {
                content.classList.add('active');
                toggle.textContent = '收起';
            }
        }

        async function verifyGeminiKey() {
            const geminiKey = document.getElementById('geminiApiKey').value;
            const statusEl = document.getElementById('geminiKeyStatus');

            if (!geminiKey) {
                statusEl.textContent = '請先輸入 API Key';
                statusEl.style.color = '#EF4444';
                return;
            }

            statusEl.textContent = '驗證中...';
            statusEl.style.color = '#94A3B8';

            try {
                const response = await fetch('/api/verify-gemini', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ api_key: geminiKey })
                });

                const result = await response.json();
                if (result.valid) {
                    statusEl.textContent = '驗證成功，儲存中...';
                    const saveResponse = await fetch('/api/settings', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ gemini_api_key: geminiKey })
                    });
                    if (saveResponse.ok) {
                        statusEl.textContent = '✓ API Key 驗證成功並已儲存！';
                        statusEl.style.color = '#059669';
                    } else {
                        statusEl.textContent = '✓ 驗證成功，但儲存失敗';
                        statusEl.style.color = '#F59E0B';
                    }
                } else {
                    statusEl.textContent = '✗ API Key 無效: ' + (result.error || '請檢查金鑰是否正確');
                    statusEl.style.color = '#EF4444';
                }
            } catch (err) {
                statusEl.textContent = '驗證失敗: 網路錯誤';
                statusEl.style.color = '#EF4444';
            }
        }

        // Load saved settings
        fetch('/api/settings').then(r => r.json()).then(data => {
            if (data.has_gemini_key) {
                document.getElementById('geminiApiKey').placeholder = '已設定 (輸入新金鑰可覆蓋)';
                document.getElementById('geminiKeyStatus').textContent = '✓ 已設定 API Key';
                document.getElementById('geminiKeyStatus').style.color = '#059669';
            }
        }).catch(() => {});

        // Add spin animation
        const style = document.createElement('style');
        style.textContent = '@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }';
        document.head.appendChild(style);
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
    <title>登入 - TrainFlow 列車流</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Nunito+Sans:wght@300;400;500;600;700&family=Varela+Round&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #10B981;
            --primary-light: #34D399;
            --secondary: #8B5CF6;
            --background: #FDF8F5;
            --text-primary: #064E3B;
            --text-secondary: #475569;
            --border: rgba(16, 185, 129, 0.15);
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Nunito Sans', -apple-system, BlinkMacSystemFont, 'Microsoft JhengHei', sans-serif;
            background: var(--background);
            background-image:
                radial-gradient(ellipse at 20% 20%, rgba(254, 205, 211, 0.4) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 80%, rgba(209, 250, 229, 0.4) 0%, transparent 50%),
                radial-gradient(ellipse at 50% 50%, rgba(139, 92, 246, 0.08) 0%, transparent 70%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .login-container {
            width: 100%;
            max-width: 420px;
        }
        .login-box {
            background: rgba(255, 255, 255, 0.9);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            padding: 48px 40px;
            border-radius: 24px;
            box-shadow: 0 20px 60px rgba(16, 185, 129, 0.12);
            border: 1px solid var(--border);
        }
        .logo {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            margin-bottom: 12px;
        }
        .logo-icon {
            width: 48px;
            height: 48px;
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
            border-radius: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3);
        }
        .logo-icon svg { width: 28px; height: 28px; color: white; }
        .logo-text {
            font-family: 'Varela Round', sans-serif;
            font-size: 26px;
            color: var(--primary);
            font-weight: 700;
        }
        .subtitle {
            text-align: center;
            color: var(--text-secondary);
            margin-bottom: 36px;
            font-size: 15px;
        }
        .form-group { margin-bottom: 24px; }
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: var(--text-primary);
            font-size: 14px;
        }
        input {
            width: 100%;
            padding: 16px 20px;
            border: 2px solid var(--border);
            border-radius: 12px;
            font-size: 16px;
            font-family: inherit;
            background: white;
            color: var(--text-primary);
            transition: all 0.2s ease;
        }
        input:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.1);
        }
        input::placeholder { color: #94A3B8; }
        button {
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3);
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(16, 185, 129, 0.4);
        }
        .error {
            background: #FEE2E2;
            color: #DC2626;
            padding: 12px 16px;
            border-radius: 10px;
            text-align: center;
            margin-bottom: 24px;
            font-size: 14px;
            border: 1px solid rgba(220, 38, 38, 0.2);
        }
        .footer-text {
            text-align: center;
            margin-top: 24px;
            color: var(--text-secondary);
            font-size: 13px;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-box">
            <div class="logo">
                <div class="logo-icon">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                </div>
                <span class="logo-text">TrainFlow</span>
            </div>
            <p class="subtitle">高鐵自動訂票系統</p>
            {% if error %}<div class="error">{{ error }}</div>{% endif %}
            <form method="POST">
                <div class="form-group">
                    <label>密碼</label>
                    <input type="password" name="password" placeholder="請輸入密碼" required>
                </div>
                <button type="submit">登入系統</button>
            </form>
            <p class="footer-text">讓訂票如流水般順暢</p>
        </div>
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
        return render_template_string(LOGIN_TEMPLATE, error='密碼錯誤')
    return render_template_string(LOGIN_TEMPLATE, error=None)


@app.route('/')
@check_auth
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})


@app.route('/api/verify-gemini', methods=['POST'])
def verify_gemini():
    """Verify if Gemini API key is valid"""
    data = request.json
    api_key = data.get('api_key', '')

    if not api_key:
        return jsonify({'valid': False, 'error': '請輸入 API Key'})

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        # Try a simple request to verify the key
        response = model.generate_content("Say 'OK' if you can read this.")
        if response and response.text:
            return jsonify({'valid': True, 'message': 'API Key 驗證成功'})
        else:
            return jsonify({'valid': False, 'error': '無法取得回應'})
    except Exception as e:
        error_msg = str(e)
        if 'API_KEY_INVALID' in error_msg or 'invalid' in error_msg.lower():
            return jsonify({'valid': False, 'error': 'API Key 無效'})
        elif 'quota' in error_msg.lower():
            return jsonify({'valid': False, 'error': '配額已用盡'})
        else:
            return jsonify({'valid': False, 'error': f'驗證失敗: {error_msg[:50]}'})


@app.route('/api/settings', methods=['GET', 'POST'])
def settings():
    global APP_PASSWORD, GEMINI_API_KEY

    if request.method == 'GET':
        return jsonify({
            'has_password': bool(APP_PASSWORD),
            'has_gemini_key': bool(GEMINI_API_KEY)
        })

    # POST - update settings
    data = request.json
    updated = []

    if data.get('password'):
        APP_PASSWORD = data['password']
        os.environ['APP_PASSWORD'] = APP_PASSWORD
        updated.append('password')

    if data.get('gemini_api_key'):
        GEMINI_API_KEY = data['gemini_api_key']
        os.environ['GEMINI_API_KEY'] = GEMINI_API_KEY
        updated.append('gemini_api_key')

    # Save to .env file for persistence
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    env_lines = []
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            env_lines = f.readlines()

    # Update or add values
    env_dict = {}
    for line in env_lines:
        if '=' in line and not line.strip().startswith('#'):
            key = line.split('=')[0].strip()
            env_dict[key] = line

    if data.get('password'):
        env_dict['APP_PASSWORD'] = f'APP_PASSWORD={APP_PASSWORD}\n'
    if data.get('gemini_api_key'):
        env_dict['GEMINI_API_KEY'] = f'GEMINI_API_KEY={GEMINI_API_KEY}\n'

    with open(env_path, 'w') as f:
        for key, line in env_dict.items():
            f.write(line)

    return jsonify({'success': True, 'updated': updated})


@app.route('/api/book', methods=['POST'])
@check_auth
def start_booking():
    global booking_status

    if booking_status['running']:
        return jsonify({'error': True, 'message': '訂票程序正在執行中'}), 400

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
        config['fields']['THSRC']['ticket']['disabled'] = int(data.get('disabled', 0))
        config['fields']['THSRC']['ticket']['elder'] = int(data.get('elder', 0))

        # Update IDs for disabled and elder passengers
        if 'ids' not in config['fields']['THSRC']:
            config['fields']['THSRC']['ids'] = {}

        # Parse disabled IDs (comma separated)
        disabled_ids_str = data.get('disabled_ids', '')
        if disabled_ids_str:
            disabled_ids = [id.strip() for id in disabled_ids_str.split(',') if id.strip()]
            config['fields']['THSRC']['ids']['disabled'] = disabled_ids

        # Parse elder IDs (comma separated)
        elder_ids_str = data.get('elder_ids', '')
        if elder_ids_str:
            elder_ids = [id.strip() for id in elder_ids_str.split(',') if id.strip()]
            config['fields']['THSRC']['ids']['elder'] = elder_ids

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
    print("台灣高鐵自動訂票系統 - Web/Docker 版本")
    print(f"{'='*60}")
    print(f"伺服器位址: http://localhost:{port}")
    print(f"密碼保護: {'已啟用' if APP_PASSWORD else '未啟用'}")
    print(f"Gemini 驗證碼辨識: {'已啟用' if GEMINI_API_KEY else '未啟用 (請設定 GEMINI_API_KEY)'}")
    print(f"{'='*60}\n")

    app.run(host='0.0.0.0', port=port, debug=debug)
