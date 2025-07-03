
# 📖 V2Ray/Xray Enterprise - The Developer's Guide

Hey there, fellow developer\! 👋

Welcome to the engine room of the **V2Ray/Xray Enterprise Tester**. We're thrilled that you're interested in peeking behind the curtain and maybe even lending a hand. This guide is designed to get you up to speed with the project's architecture, core components, and development workflow.

[](https://github.com/Shayanthn/V2ray-Tester-Pro)
[](https://www.google.com/search?q=https://github.com/Shayanthn/V2ray-Tester-Pro/blob/main/LICENSE)
[](https://www.python.org/downloads/)
[](https://riverbankcomputing.com/software/pyqt/)
[](https://github.com/Shayanthn/V2ray-Tester-Pro/tree/developer-mode)

-----

## Table of Contents

  * [🚀 Project Philosophy](https://github.com/Shayanthn/V2ray-Tester-Pro/tree/developer-mode?tab=readme-ov-file#-project-philosophy)
  * [🏗️ High-Level Architecture](https://github.com/Shayanthn/V2ray-Tester-Pro/tree/developer-mode?tab=readme-ov-file#%EF%B8%8F-high-level-architecture)
  * [🧩 Core Components Deep Dive](https://github.com/Shayanthn/V2ray-Tester-Pro/tree/developer-mode?tab=readme-ov-file#-core-components-deep-dive)
  * [🛠️ Setting Up Your Dev Environment](https://github.com/Shayanthn/V2ray-Tester-Pro/tree/developer-mode?tab=readme-ov-file#%EF%B8%8F-setting-up-your-dev-environment)
  * [🔄 The Testing Workflow](https://github.com/Shayanthn/V2ray-Tester-Pro/tree/developer-mode?tab=readme-ov-file#-the-testing-workflow)
  * [🧠 Key Concepts & Design Patterns](https://github.com/Shayanthn/V2ray-Tester-Pro/tree/developer-mode?tab=readme-ov-file#-key-concepts--design-patterns)
  * [🤝 How to Contribute](https://github.com/Shayanthn/V2ray-Tester-Pro/tree/developer-mode?tab=readme-ov-file#-how-to-contribute)
  * [🗺️ Future Roadmap](https://github.com/Shayanthn/V2ray-Tester-Pro/tree/developer-mode?tab=readme-ov-file#%EF%B8%8F-future-roadmap)
  * [📞 Get In Touch](https://github.com/Shayanthn/V2ray-Tester-Pro/tree/developer-mode?tab=readme-ov-file#-get-in-touch)

-----

## 🚀 Project Philosophy

Our goal was to build more than just a "tester." We aimed for a tool that is **powerful, scalable, and secure**. We're guided by four core principles:

1.  **Modularity:** Every piece of the application has a specific job. This makes the code easier to understand, maintain, and extend.
2.  **Performance:** We leverage `asyncio` and multithreading to run a massive number of tests concurrently without freezing the user interface. Speed is a feature.
3.  **Security:** We don't blindly trust configs from the internet. Every URI and config is validated to prevent malicious code execution.
4.  **User Experience:** We provide two rich interfaces—a graphical one with **PyQt6** and a beautiful terminal UI with **Rich**—to cater to every kind of user.

-----

## 🏗️ High-Level Architecture

The application is built in layers to separate concerns, making it clean and manageable.

```
+--------------------------------+
|         UI Layer               |
|  (MainWindow / CLIDashboard)   |
+--------------------------------+
             ^
             | (Signals/Slots, Callbacks)
             v
+--------------------------------+
|      Application Logic         |
| (BackendWorker, TestOrchestrator)|
+--------------------------------+
             ^
             | (Async Tasks, Thread Pool)
             v
+--------------------------------+
|       Core Testing Engine      |
| (ConfigProcessor, TestRunner)  |
+--------------------------------+
             ^
             | (Subprocess Call)
             v
+--------------------------------+
|    Xray Core (xray.exe)        |
+--------------------------------+
```

-----

## 🧩 Core Components Deep Dive

Here's a breakdown of the key classes and what they do.

| Class/Module | Role & Responsibility |
| :--- | :--- |
| `EnterpriseConfig` | **The Mastermind.** Manages all application settings, from test URLs to config sources and Telegram credentials. |
| `AppState` | **The Global State.** A centralized place to track the app's current state (running, progress, results, etc.). |
| `NetworkManager` | **The Network Guru.** Handles all network requests (`aiohttp`) with robust retry logic and DoH support. |
| `SecurityValidator` | **The Security Guard.** Validates URIs and JSON configs to block malicious payloads and blacklisted addresses. |
| `ConfigProcessor` | **The Config Engine.** The heart of the parsing logic. It masterfully converts various URI schemes into a full JSON format that Xray understands. |
| `ConfigDiscoverer`| **The Source Explorer.** Finds and fetches config lists from aggregator links and direct subscription sources. |
| `TestRunner` | **The Test Executor.** Spawns the Xray process and runs a suite of tests (ping, speed, bypass) on a single config. |
| `TestOrchestrator`| **The Conductor.** Manages the entire testing pipeline, from creating the config queue to managing the worker pool. |
| `BackendWorker` | **The GUI's Best Friend.** Runs the entire testing pipeline in a separate `QThread` to keep the UI smooth and responsive. |
| `MainWindow` | **The Graphical UI.** The main application window, built with PyQt6, handling all user interactions and data display. |
| `CLIDashboard` | **The Terminal UI.** A beautiful and functional command-line interface powered by the `Rich` library. |
| `TelegramManager` | **The Messenger.** Manages all interactions with the Telegram bot, from handling commands to broadcasting results. |

-----

## 🛠️ Setting Up Your Dev Environment

Ready to get your hands dirty? Here’s how to get up and running.

1.  **Prerequisites:**

      * Git
      * Python 3.8+
      * `venv` or `conda` for environment management (highly recommended).

2.  **Clone the Developer Branch:**
    Make sure you're working on the `developer-mode` branch, which contains the latest source code.

    ```bash
    git clone --branch developer-mode https://github.com/Shayanthn/V2ray-Tester-Pro.git
    cd V2ray-Tester-Pro
    ```

3.  **Set Up Your Virtual Environment:**

      * **Using `venv` (recommended):**
        ```bash
        python -m venv venv
        # On Windows
        .\venv\Scripts\activate
        # On macOS/Linux
        source venv/bin/activate
        ```

4.  **Install Dependencies:**
    We've included a `requirements.txt` file to make this easy.

    ```bash
    pip install -r requirements.txt
    ```

    > **Note:** If the file is missing, you can create it with the following content:
    > `aiohttp, psutil, requests, python-dotenv, PyQt6, rich, python-telegram-bot`

5.  **Get the Xray Core:**
    Download the latest Xray core binary from the [official Xray-core releases](https://github.com/XTLS/Xray-core/releases). Place the executable in the project's root directory and name it `xray.exe` (for Windows) or `xray` (for Linux/macOS).

6.  **(Optional) Create a `.env` file:**
    To use features like the Telegram bot, create a `.env` file in the root directory. You can copy the contents of `.env.example` (if it exists) or use the template below.

    ```env
    # .env file for local development

    # Telegram Bot Token from BotFather
    TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"

    # Your personal Telegram User ID for admin commands
    TELEGRAM_ADMIN_ID="YOUR_TELEGRAM_ADMIN_ID"

    # Comma-separated list of channel/user IDs to send results to
    TELEGRAM_TARGET_IDS="@your_channel,12345678"
    ```

You're all set\! Run the application:

  * `python main.py` for the GUI.
  * `python main.py --cli` for the terminal interface.

-----

## 🔄 The Testing Workflow

Understanding the data flow is key to debugging and extending the app.

1.  **`TestOrchestrator.run_test_pipeline()`** is called to kick things off.
2.  **Discover (`ConfigDiscoverer`):** Gathers all subscription links from direct sources and aggregators.
3.  **Fetch & Queue (`_fetch_and_queue_configs`):** Downloads and decodes all configs, validates them for security (`SecurityValidator`), and pushes the safe ones into an `asyncio.Queue`.
4.  **Spawn Workers (`_run_workers`):** A pool of worker tasks is created to process the queue concurrently.
5.  **Process a URI (`_worker`):**
      * A URI is pulled from the queue.
      * `ConfigProcessor` turns the URI into a full Xray JSON config.
      * `TestRunner` saves this JSON to a temp file, spawns the `xray.exe` process with it, and runs ping/speed tests through the local SOCKS proxy.
      * A dictionary containing the results is returned.
6.  **Handle Result:**
      * The server's GeoIP location is fetched.
      * The final result is sent to the UI via a PyQt Signal (`result_ready`).
      * Global stats in `AppState` are updated.
7.  **Finish:** Once the queue is empty, workers are stopped, and final results are saved or broadcasted.

-----

## 🧠 Key Concepts & Design Patterns

  * **Asynchronous I/O (`asyncio`):** We use `asyncio` for all network-bound operations (downloading configs, DoH lookups, fetching GeoIP data). This allows the app to handle hundreds of I/O tasks at once without waiting, dramatically boosting performance.
  * **Threading & Concurrency:**
      * **`QThread`:** The `BackendWorker` runs the entire `asyncio` event loop on a separate thread, ensuring the GUI never freezes, even under heavy load.
      * **`ThreadPoolExecutor`:** We use a thread pool to run the synchronous, blocking `TestRunner` function from within our async code. This is a classic pattern for integrating blocking code into an `asyncio` application.
      * **`subprocess.Popen`:** The Xray core itself is run as a completely separate process, which is the cleanest and most reliable way to manage it.
  * **Observer Pattern:** The **Signals & Slots** mechanism in PyQt6 is a fantastic implementation of this pattern. The backend (`BackendWorker`) *emits* signals like `update_status` or `result_ready` without knowing anything about the UI. The frontend (`MainWindow`) *subscribes* to these signals and updates itself accordingly. This decoupling makes the code incredibly clean.

-----

## 🤝 How to Contribute

Contributions are what make the open-source community amazing. We welcome any help\!

1.  **Reporting Bugs:** Found an issue? Open a new issue in the [GitHub Issues](https://www.google.com/search?q=https://github.com/Shayanthn/V2ray-Tester-Pro/issues) section. Please be as detailed as possible.
2.  **Suggesting Enhancements:** Have a great idea? Open an issue and let's discuss it.
3.  **Pull Requests:**
      * Fork the repository.
      * Create a new feature branch: `git checkout -b feature/your-cool-feature`
      * Make your changes and commit them with a clear message.
      * Push to your fork and submit a **Pull Request** to our `developer-mode` branch.

-----

## 🗺️ Future Roadmap

We have big plans\! Here are some ideas we're exploring. Feel free to grab one and contribute\!

  * [ ] **Support for More Protocols:** Add parsers for other emerging protocols.
  * [ ] **Advanced Analytics:** Implement charting and graphing to visualize test results over time.
  * [ ] **Plugin System:** Allow developers to write their own test modules or result exporters.
  * [ ] **GitHub Actions CI/CD:** Automate the process of building and releasing the `.exe` for Windows, macOS, and Linux.
  * [ ] **Better Dark/Light Theme Support:** Enhance the GUI theming.

-----

## 📞 Get In Touch

Have questions, want to collaborate, or just want to say hi? I'd love to hear from you.

  * **Website:** [shayantaherkhani.ir](https://shayantaherkhani.ir)
  * **Email:** [shayanthn78@gmail.com](mailto:shayanthn78@gmail.com) | [admin@shayantaherkhani.ir](mailto:admin@shayantaherkhani.ir)

Thanks for being a part of this project. Let's build something amazing together\! ❤️
