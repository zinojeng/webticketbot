# THSRC Ticket Bot - 開發進度報告

> 最後更新：2026-01-18

---

## 專案概述

| 專案 | 路徑 | 連線方式 |
|------|------|----------|
| Local CLI | `/Users/zino/Desktop/OpenAI/Ticket-Bot-main/` | httpx (無瀏覽器) |
| Web/Docker | `/Volumes/WD_BLACK/OpenAI/webticketbot/` | Selenium + Chrome |

---

## 目前進度

### 已完成功能

#### 1. Web 介面重新設計 (TrainFlow 列車流)
- [x] 全新 UI 設計：採用 Soft UI Evolution 風格
- [x] 響應式設計，支援桌面與行動裝置
- [x] 浮動式導覽列、Hero 區塊、服務介紹
- [x] 操作說明區塊（三步驟流程）
- [x] 顧客評價區塊
- [x] 主題色系：綠色 (#10B981) + 紫色 (#8B5CF6)
- [x] 字體：Varela Round + Nunito Sans

#### 2. 驗證碼辨識系統 (Dual OCR)
- [x] 主要方案：holey.cc API (`https://ocr.holey.cc/thsrc`)
- [x] 備援方案：Google Gemini Vision API (`gemini-2.0-flash-exp`)
- [x] 自動切換：holey.cc 失敗時自動使用 Gemini
- [x] 驗證碼擷取：使用 Selenium `screenshot_as_png`（解決 httpx 逾時問題）

#### 3. Selenium 自動化
- [x] Chrome WebDriver 初始化（支援 Docker headless 模式）
- [x] 頁面載入與等待機制
- [x] 驗證碼圖片擷取
- [x] 表單填寫（使用 JavaScript 注入避免 overlay 攔截）

#### 4. 基礎建設
- [x] Dockerfile（含 Chrome 安裝）
- [x] Flask Web 介面
- [x] 密碼保護（`APP_PASSWORD` 環境變數）
- [x] 即時日誌串流
- [x] 背景執行緒訂票

### 進行中 / 待修復

#### 1. 表單元素選擇器問題
- **問題**：THSRC 網站有 `.mTop` overlay 會攔截點擊事件
- **狀態**：已加入 `_dismiss_overlays()` 函數嘗試隱藏 overlay
- **狀態**：已改用 JavaScript 執行所有點擊與值設定
- **待驗證**：需要實際測試確認是否解決

#### 2. 訂票方法選擇器
- **原問題**：使用 `By.ID, 'bookingMethod1'` 找不到元素
- **已修正**：改用 `By.CSS_SELECTOR, 'input[name="bookingMethod"][value="radio31"]'`
- **說明**：`radio31` = 時間搜尋，`radio33` = 車次搜尋

---

## 檔案結構

```
webticketbot/
├── web_app.py              # Flask Web 介面（主要進入點）
├── ticket_bot.py           # CLI 進入點
├── services/
│   ├── base_service.py     # Selenium WebDriver 初始化
│   └── thsrc.py            # THSRC 訂票邏輯（Selenium 版本）
├── utils/
│   ├── captcha_ocr.py      # 雙重 OCR 系統
│   ├── validate.py         # 身分證驗證
│   └── io.py               # 檔案 I/O
├── configs/
│   ├── config.py           # 應用程式設定
│   └── THSRC.toml          # THSRC 服務設定
├── Dockerfile              # Docker 設定（含 Chrome）
├── requirements.txt        # Python 依賴
├── zeabur.json             # Zeabur 部署設定
└── user_config.toml        # 使用者設定
```

---

## 未來方向

### 短期目標

1. **修復表單填寫問題**
   - 確認 `_dismiss_overlays()` 能正確隱藏所有干擾元素
   - 測試完整訂票流程（從搜尋到確認）

2. **改善錯誤處理**
   - 加入更詳細的日誌輸出
   - 提供使用者友善的錯誤訊息

3. **驗證碼辨識優化**
   - 收集辨識失敗的案例
   - 調整 Gemini prompt 提升準確率

### 中期目標

1. **支援更多功能**
   - 來回票訂購
   - 多人同時訂票
   - 票種選擇（早鳥、學生票等）

2. **通知系統**
   - 訂票成功後發送 Email / LINE 通知
   - 即時狀態推播

3. **排程功能**
   - 設定時間自動開始搶票
   - 開放訂票前自動準備

### 長期目標

1. **多平台支援**
   - 台鐵訂票整合
   - 客運訂票整合

2. **使用者帳號系統**
   - 儲存常用乘車資訊
   - 訂票歷史記錄

---

## 可能的改善想法

### 技術面

1. **改用 Playwright 取代 Selenium**
   - 優點：更現代、更快、更穩定
   - 支援自動等待、更好的錯誤處理
   - 內建支援 headless 模式

2. **驗證碼預取機制**
   - 在使用者填寫表單時預先辨識驗證碼
   - 減少等待時間

3. **WebSocket 即時日誌**
   - 目前使用 polling 方式取得日誌
   - 改用 WebSocket 可減少延遲

4. **分散式架構**
   - 多個 Worker 同時嘗試
   - 提高搶票成功率

### 使用者體驗

1. **表單驗證強化**
   - 即時驗證身分證格式
   - 日期選擇器優化

2. **深色模式**
   - 目前僅有淺色主題
   - 可加入深色模式切換

3. **多語系支援**
   - 目前僅支援繁體中文
   - 可加入英文介面

### 部署與維運

1. **Docker 映像優化**
   - 減少映像大小
   - 使用 multi-stage build

2. **健康檢查端點**
   - 加入 `/health` API
   - 便於監控服務狀態

3. **環境變數管理**
   - 使用 `.env.example` 範本
   - 文件化所有環境變數

---

## 已知問題

| 問題 | 狀態 | 說明 |
|------|------|------|
| `.mTop` overlay 攔截點擊 | 修復中 | 已加入 `_dismiss_overlays()` |
| holey.cc 偶爾逾時 | 已修復 | 改用 Selenium screenshot |
| 表單選擇器不匹配 | 已修復 | 改用正確的 CSS selector |
| 驗證碼辨識率 | 觀察中 | Gemini 備援提升準確率 |

---

## 測試指令

### Web 版本本地測試
```bash
cd /Volumes/WD_BLACK/OpenAI/webticketbot
python web_app.py
# 開啟 http://localhost:8080
```

### Docker 測試
```bash
cd /Volumes/WD_BLACK/OpenAI/webticketbot
docker build -t webticketbot .
docker run -e APP_PASSWORD=test -e GEMINI_API_KEY=your_key -p 8080:8080 webticketbot
```

### Zeabur 部署
1. Push 至 GitHub
2. 連接 Zeabur
3. 設定環境變數：`APP_PASSWORD`、`GEMINI_API_KEY`
4. 部署並測試

---

## 更新日誌

### 2026-01-18
- 重新設計 Web 介面（TrainFlow 主題）
- 修復驗證碼擷取逾時問題（改用 Selenium screenshot）
- 修復表單元素選擇器（bookingMethod radio31/radio33）
- 加入 overlay 隱藏機制（_dismiss_overlays）
- 改用 JavaScript 執行表單操作
- 加入詳細日誌輸出

### 初始版本
- 基礎 Selenium 自動化
- Flask Web 介面
- Dual OCR 系統（holey.cc + Gemini）
- Docker 支援

---

## 相關連結

- **GitHub**: https://github.com/zinojeng/webticketbot
- **參考版本**: Local CLI (`/Users/zino/Desktop/OpenAI/Ticket-Bot-main/`)
