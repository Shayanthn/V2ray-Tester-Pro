# V2Ray Tester Pro

![Version](https://img.shields.io/badge/version-5.1.2-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

**V2Ray Tester Pro** is an advanced, enterprise-grade tool for testing, filtering, and managing V2Ray/Xray configurations. It allows you to scan thousands of subscription links, verify their connectivity, measure speed (ping/download/upload), and export the working configurations.

## 🚀 New in v5.1.2

- **Modern GUI**: A completely redesigned interface with a dark theme, sidebar navigation, and dashboard.
- **Dashboard**: Real-time statistics on total configs, working servers, and average ping.
- **QR Code & Sharing**: Right-click on any result to generate a QR code or copy the configuration link.
- **Performance**: Optimized testing engine with lower resource usage.

## ✨ Features

- **Protocol Support**: VMess, VLESS, Trojan, Shadowsocks.
- **High Performance**: Asynchronous testing engine capable of handling thousands of configs.
- **Smart Filtering**: Automatically removes duplicates and invalid configurations.
- **Security**: Built-in security validator to block malicious payloads.
- **GeoIP**: Detects server location (Country).
- **Export**: Save results to JSON or copy directly to clipboard.

## 🛠️ Installation

### Prerequisites
- Windows 10/11 (64-bit)
- [Python 3.11+](https://www.python.org/downloads/) (if running from source)

### Running the Executable
1. Download the latest `V2Ray-Tester-Pro.exe` from the [Releases](https://github.com/yourusername/V2ray-Tester-Pro/releases) page.
2. Ensure `xray.exe` and `geoip.dat` are in the same folder (or let the app download them).
3. Run the application.
   > **Note:** If you see a "Windows protected your PC" warning, click **More info** and then **Run anyway**. This happens because the app does not have a paid digital signature yet.

### Running from Source
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/V2ray-Tester-Pro.git
   cd V2ray-Tester-Pro
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python main.py
   ```

## 📖 Usage Guide

### Dashboard
The **Dashboard** gives you a quick overview of the current session. It shows the total number of configurations loaded and how many are currently working.

### Scan & Test
1. Go to the **Scan & Test** tab.
2. Click **Start New Scan**. The application will automatically fetch configurations from the defined sources (subscriptions).
3. Watch the progress bar and status log.

### Results
1. Go to the **Results Table** tab to see the working configurations.
2. **Right-click** on any row to:
   - **Copy Link**: Copy the `vless://` or `vmess://` link to your clipboard.
   - **Show QR Code**: Display a QR code to scan with your mobile V2Ray client (e.g., v2rayNG, Streisand).

## 🏗️ Building from Source

To create a standalone `.exe` file:

1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```
2. Run the build command:
   ```bash
   pyinstaller build.spec --clean --noconfirm
   ```
3. The executable will be generated in the `dist/` folder.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
