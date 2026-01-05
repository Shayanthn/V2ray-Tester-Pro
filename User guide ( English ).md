<div align="center">
  <img src="https://github.com/Shayanthn/V2ray-Tester-Pro/blob/media/Guide.gif" alt="V2Ray Tester Pro" width="700"/>
  <br/><br/>
  <h1>V2Ray/Xray Tester Pro</h1>
  <h2>Complete User Guide</h2>
</div>

<p align="center">
Welcome! This guide helps you easily use all features of the app and find the best configurations.
</p>

---

## 📋 Table of Contents

1. [🚀 Getting Started](#-getting-started)
2. [🖥️ Main Window Overview](#️-main-window-overview)
3. [▶️ How to Use](#️-how-to-use)
4. [⚙️ Customizing the App](#️-customizing-the-app)
5. [🤖 Using the Telegram Bot](#-using-the-telegram-bot)
6. [❓ FAQ](#-faq)
7. [🤝 Contact & Support](#-contact--support)

---

## 🚀 Getting Started

Follow these two simple steps to start using the app:

### 1. Download release 

-  the `xray` is on file . 
- If you see **Xray core not found**, the file is missing or in the wrong location.

> 💡 **Note:** The app will not work without this file.

### 2. Run the Application

- Double-click the executable file (e.g., `V2RayTesterPro.exe`).
- The main window will open.

---

## 🖥️ Main Window Overview

The application now features a modern, dark-themed interface with a sidebar for easy navigation.

### 📑 Sidebar Navigation

- **Dashboard**: View real-time statistics (Total Configs, Working Configs, Avg Ping).
- **Scan & Test**: The main control center to start/stop scans and view logs.
- **Results Table**: A detailed list of all working configurations found.

### 📊 Dashboard

The dashboard provides a quick summary of your current session:
- **Total Configs**: Number of links fetched from subscriptions.
- **Working**: Number of valid, working configurations found.
- **Avg Ping**: The average latency of working servers.

### 🔍 Scan & Test Page

- **Start New Scan**: Begins the process of fetching and testing configurations.
- **Stop Scanning**: Halts the current operation.
- **Progress Bar**: Shows the completion percentage.
- **Status Log**: Displays real-time actions (e.g., "Testing: vless://...").

### 📝 Results Table

Displays the successful configurations with details:
- **Protocol**: (vmess, vless, trojan, etc.)
- **Address**: Server IP or Domain.
- **Ping**: Latency in milliseconds.
- **Download/Upload**: Speed test results.
- **Country**: Server location.

**Right-Click Menu:**
- **Copy Link**: Copy the configuration link to clipboard.
- **Show QR Code**: Generate a QR code for mobile scanning.
- 📊 **Statistics:** Show test statistics
- ⚙️ **Settings:** Open settings

### 🔍 Search and Filter Tools

- **Search bar:** Instantly filter results
- **Protocol & Country filters:** Narrow down displayed configs

### 📋 Results Table

| Column | Description |
|---|---|
| Protocol | Type of config |
| Address | Server address |
| Country | Server location |
| Ping (ms) | Response time |
| Jitter (ms) | Ping fluctuation |
| DL/UL (Mbps) | Download/Upload speed |
| Bypassing | Can bypass filtering |

### 📈 Status Bar

- Left: Current app status
- Center: Currently tested config
- Right: Progress percentage

---

## ▶️ How to Use

### 🟢 Starting a Test

1. Click **Start Test**.
2. Results will appear gradually.

### 📑 Working with Results

- Sort by clicking on column headers
- Right-click a row to:
  - **Copy URI:** Copy the full config link
  - **Copy Address:** Copy server address
  - **View Config JSON:** See full details
  - **Share via Telegram:** Send to Telegram
  - **Open Location Info:** View IP details

### 💾 Exporting / Importing

- **Export:** Save selected configs
- **Import:** Load configs from a file

---

## ⚙️ Customizing the App

### 🧪 Testing Tab

- **Max Concurrent Tests:** Number of parallel tests
- **Test Timeout:** Time to wait per server

### 🌐 Sources Tab

- **Aggregator Links:** Links containing more sources
- **Direct Subscription Links:** Direct subscription URLs

### ✈️ Telegram Tab

- **Bot Token:** Your bot's token
- **Admin User ID:** Your Telegram user ID
- **Target IDs:** Where to send reports

### 🤖 Adaptive Tab

- Enable smart testing based on network quality

---

## 🤖 Using the Telegram Bot

| Command | Description |
|---|---|
| `/start_test` | Start a new test |
| `/stop_test` | Stop current test |
| `/status` | Show current progress |
| `/results` | Display top configs |
| `/stats` | Show overall stats |

---

## ❓ FAQ

**Q: Xray file not found?**  
✅ Make sure `xray` is next to the executable.

**Q: No results after testing?**  
✅ Check your internet connection or config sources.

**Q: Where do I get the bot token and user ID?**  
✅ From `@BotFather` and `@userinfobot` in Telegram.

---

## 🤝 Contact & Support

For any questions or collaboration: shayantaherkhani.ir

<div align="center">
<strong>Developed with ❤️ by Shayan Taherkhani</strong>
</div>
