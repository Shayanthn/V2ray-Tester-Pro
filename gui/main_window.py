import sys
import logging
import qrcode
import io
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QProgressBar, QTableWidget, 
    QTableWidgetItem, QHeaderView, QStatusBar, QMessageBox,
    QFrame, QStackedWidget, QButtonGroup, QGridLayout, QMenu, QDialog
)
from PyQt6.QtCore import Qt, pyqtSlot, QSize
from PyQt6.QtGui import QIcon, QFont, QColor, QPixmap, QImage, QAction

from core.app_state import AppState
from gui.worker import Worker
from config.enterprise_config import EnterpriseConfig
from gui.styles import ModernStyles

class MainWindow(QMainWindow):
    """Main GUI Window with Modern Sidebar Layout."""
    
    def __init__(self, 
                 app_state: AppState, 
                 worker_factory, 
                 config: EnterpriseConfig,
                 logger: logging.Logger):
        super().__init__()
        self.app_state = app_state
        self.worker_factory = worker_factory
        self.config = config
        self.logger = logger
        self.worker = None
        
        self.init_ui()
        
    def init_ui(self):
        """Initialize the modern user interface."""
        self.setWindowTitle(f"{self.config.APP_NAME} v{self.config.APP_VERSION}")
        self.setGeometry(100, 100, 1100, 750)
        if self.config.ICON_PATH:
            self.setWindowIcon(QIcon(self.config.ICON_PATH))
            
        # Apply Dark Theme
        self.setStyleSheet(ModernStyles.DARK_THEME)
            
        # Main Container
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 1. Sidebar
        self.sidebar = self.create_sidebar()
        main_layout.addWidget(self.sidebar)
        
        # 2. Content Area (Stacked Widget)
        self.content_area = QFrame()
        self.content_area.setObjectName("Content")
        content_layout = QVBoxLayout(self.content_area)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        self.pages = QStackedWidget()
        content_layout.addWidget(self.pages)
        
        # Create Pages
        self.dashboard_page = self.create_dashboard_page()
        self.scan_page = self.create_scan_page()
        self.results_page = self.create_results_page()
        
        self.pages.addWidget(self.dashboard_page)
        self.pages.addWidget(self.scan_page)
        self.pages.addWidget(self.results_page)
        
        main_layout.addWidget(self.content_area)
        
        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def create_sidebar(self):
        """Creates the left navigation sidebar."""
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 20, 0, 20)
        layout.setSpacing(5)
        
        # App Title in Sidebar
        title = QLabel("V2Ray Tester")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: white; padding-left: 20px; margin-bottom: 20px;")
        layout.addWidget(title)
        
        # Navigation Buttons
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        
        btn_dashboard = self.create_nav_btn("Dashboard", 0)
        btn_scan = self.create_nav_btn("Scan & Test", 1)
        btn_results = self.create_nav_btn("Results Table", 2)
        
        layout.addWidget(btn_dashboard)
        layout.addWidget(btn_scan)
        layout.addWidget(btn_results)
        
        layout.addStretch()
        
        # Version Label
        version = QLabel(f"v{self.config.APP_VERSION}")
        version.setStyleSheet("color: #666; padding-left: 20px;")
        layout.addWidget(version)
        
        # Set default
        btn_dashboard.setChecked(True)
        
        return sidebar

    def create_nav_btn(self, text, index):
        """Helper to create sidebar buttons."""
        btn = QPushButton(text)
        btn.setObjectName("SidebarBtn")
        btn.setCheckable(True)
        btn.clicked.connect(lambda: self.pages.setCurrentIndex(index))
        self.nav_group.addButton(btn)
        return btn

    def create_dashboard_page(self):
        """Creates the Dashboard page with summary cards."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        title = QLabel("Dashboard")
        title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Cards Layout
        cards_layout = QGridLayout()
        
        self.card_total = self.create_info_card("Total Configs", "0")
        self.card_working = self.create_info_card("Working", "0")
        self.card_avg_ping = self.create_info_card("Avg Ping", "-")
        
        cards_layout.addWidget(self.card_total, 0, 0)
        cards_layout.addWidget(self.card_working, 0, 1)
        cards_layout.addWidget(self.card_avg_ping, 0, 2)
        
        layout.addLayout(cards_layout)
        layout.addStretch()
        return page

    def create_info_card(self, title_text, value_text):
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        
        t = QLabel(title_text)
        t.setObjectName("CardTitle")
        v = QLabel(value_text)
        v.setObjectName("CardValue")
        
        layout.addWidget(t)
        layout.addWidget(v)
        return card

    def create_scan_page(self):
        """Creates the Scan page with controls."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        title = QLabel("Scan Configuration")
        title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Controls Container
        controls = QFrame()
        controls.setObjectName("Card")
        c_layout = QHBoxLayout(controls)
        
        self.start_btn = QPushButton("Start New Scan")
        self.start_btn.setObjectName("ActionBtn")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.clicked.connect(self.start_test)
        
        self.stop_btn = QPushButton("Stop Scanning")
        self.stop_btn.setObjectName("StopBtn")
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.clicked.connect(self.stop_test)
        self.stop_btn.setEnabled(False)
        
        c_layout.addWidget(self.start_btn)
        c_layout.addWidget(self.stop_btn)
        layout.addWidget(controls)
        
        # Progress Section
        layout.addSpacing(20)
        self.status_label = QLabel("Ready to scan")
        self.status_label.setStyleSheet("font-size: 16px; color: #cccccc;")
        layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimumHeight(20)
        layout.addWidget(self.progress_bar)
        
        layout.addStretch()
        return page

    def create_results_page(self):
        """Creates the Results page with the table."""
        page = QWidget()
        layout = QVBoxLayout(page)
        
        title = QLabel("Scan Results")
        title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        layout.addWidget(title)
        
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Protocol", "Address", "Ping (ms)", "Download", "Upload", "Country"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        layout.addWidget(self.table)
        return page

    def show_context_menu(self, position):
        """Shows context menu for table rows."""
        menu = QMenu()
        copy_action = QAction("Copy Link", self)
        qr_action = QAction("Show QR Code", self)
        
        menu.addAction(copy_action)
        menu.addAction(qr_action)
        
        action = menu.exec(self.table.viewport().mapToGlobal(position))
        
        if action == copy_action:
            self.copy_link()
        elif action == qr_action:
            self.show_qr_code()

    def get_selected_uri(self):
        """Helper to get URI from selected row."""
        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 0)
            if item:
                return item.data(Qt.ItemDataRole.UserRole)
        return None

    def copy_link(self):
        uri = self.get_selected_uri()
        if uri:
            QApplication.clipboard().setText(uri)
            self.status_bar.showMessage("Link copied to clipboard!", 3000)

    def show_qr_code(self):
        uri = self.get_selected_uri()
        if not uri:
            return
            
        # Generate QR
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to QPixmap
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        qimg = QImage.fromData(buffer.getvalue())
        pixmap = QPixmap.fromImage(qimg)
        
        # Show Dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("QR Code")
        dialog.setFixedSize(400, 400)
        layout = QVBoxLayout(dialog)
        
        label = QLabel()
        label.setPixmap(pixmap.scaled(350, 350, Qt.AspectRatioMode.KeepAspectRatio))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        
        dialog.exec()

    # --- Logic Methods ---

    def start_test(self):
        if self.app_state.is_running:
            return
            
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.pages.setCurrentIndex(1) # Switch to Scan page
        
        # Reset Dashboard
        self.update_dashboard_card(self.card_total, "0")
        self.update_dashboard_card(self.card_working, "0")
        
        self.worker = self.worker_factory()
        self.worker.update_progress.connect(self.update_progress)
        self.worker.update_status.connect(self.update_status)
        self.worker.result_ready.connect(self.add_result)
        self.worker.finished.connect(self.on_finished)
        self.worker.current_test.connect(self.update_current_test)
        
        self.worker.start()
        
    def stop_test(self):
        if self.app_state.is_running:
            self.app_state.stop_signal.set()
            self.status_label.setText("Stopping...")
            self.stop_btn.setEnabled(False)
            
    @pyqtSlot(int)
    def update_progress(self, value):
        if self.app_state.total > 0:
            percent = int((value / self.app_state.total) * 100)
            self.progress_bar.setValue(percent)
            # Update Dashboard Total
            self.update_dashboard_card(self.card_total, str(self.app_state.total))
            
    @pyqtSlot(str)
    def update_status(self, text):
        self.status_label.setText(text)
        
    @pyqtSlot(str)
    def update_current_test(self, text):
        self.status_bar.showMessage(f"Testing: {text}")
        
    @pyqtSlot(dict)
    def add_result(self, result):
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # Store URI in the first item's user data
        protocol_item = QTableWidgetItem(str(result.get("protocol")))
        protocol_item.setData(Qt.ItemDataRole.UserRole, result.get("uri"))
        
        self.table.setItem(row, 0, protocol_item)
        self.table.setItem(row, 1, QTableWidgetItem(str(result.get("address"))))
        self.table.setItem(row, 2, QTableWidgetItem(str(result.get("ping"))))
        self.table.setItem(row, 3, QTableWidgetItem(str(result.get("download_speed"))))
        self.table.setItem(row, 4, QTableWidgetItem(str(result.get("upload_speed"))))
        self.table.setItem(row, 5, QTableWidgetItem(str(result.get("country"))))
        
        # Update Dashboard Working Count
        self.update_dashboard_card(self.card_working, str(self.app_state.found))
        
    @pyqtSlot()
    def on_finished(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Finished.")
        self.status_bar.showMessage("Ready")
        
        QMessageBox.information(self, "Test Complete", f"Found {self.app_state.found} working configs.")
        
        # Switch to results page automatically
        self.pages.setCurrentIndex(2)

    def update_dashboard_card(self, card_widget, value):
        """Helper to update card value."""
        # Find the value label (2nd item in layout)
        value_label = card_widget.findChild(QLabel, "CardValue")
        if value_label:
            value_label.setText(value)
