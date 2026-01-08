
class ModernStyles:
    DARK_THEME = """
    QMainWindow {
        background-color: #1e1e1e;
        color: #ffffff;
    }
    QWidget {
        background-color: #1e1e1e;
        color: #ffffff;
        font-family: "Segoe UI", "Roboto", sans-serif;
        font-size: 14px;
    }
    
    /* Sidebar */
    QFrame#Sidebar {
        background-color: #252526;
        border-right: 1px solid #333333;
        min-width: 200px;
        max-width: 200px;
    }
    QPushButton#SidebarBtn {
        background-color: transparent;
        color: #cccccc;
        border: none;
        text-align: left;
        padding: 15px 20px;
        font-size: 15px;
        border-left: 3px solid transparent;
    }
    QPushButton#SidebarBtn:hover {
        background-color: #2a2d2e;
        color: #ffffff;
    }
    QPushButton#SidebarBtn:checked {
        background-color: #37373d;
        color: #ffffff;
        border-left: 3px solid #007acc;
        font-weight: bold;
    }
    
    /* Content Area */
    QFrame#Content {
        background-color: #1e1e1e;
    }
    
    /* Buttons */
    QPushButton#ActionBtn {
        background-color: #007acc;
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        font-weight: bold;
    }
    QPushButton#ActionBtn:hover {
        background-color: #0062a3;
    }
    QPushButton#ActionBtn:disabled {
        background-color: #333333;
        color: #888888;
    }
    QPushButton#StopBtn {
        background-color: #d32f2f;
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        font-weight: bold;
    }
    QPushButton#StopBtn:hover {
        background-color: #b71c1c;
    }
    
    /* Table */
    QTableWidget {
        background-color: #252526;
        gridline-color: #333333;
        border: none;
        selection-background-color: #094771;
        selection-color: white;
    }
    QHeaderView::section {
        background-color: #333333;
        color: #cccccc;
        padding: 5px;
        border: none;
        border-right: 1px solid #252526;
        border-bottom: 1px solid #252526;
    }
    QTableCornerButton::section {
        background-color: #333333;
    }
    
    /* Progress Bar */
    QProgressBar {
        border: none;
        background-color: #333333;
        height: 10px;
        border-radius: 5px;
        text-align: center;
    }
    QProgressBar::chunk {
        background-color: #007acc;
        border-radius: 5px;
    }
    
    /* Cards/Panels */
    QFrame#Card {
        background-color: #252526;
        border-radius: 8px;
        padding: 15px;
    }
    QLabel#CardTitle {
        font-size: 12px;
        color: #aaaaaa;
        font-weight: bold;
    }
    QLabel#CardValue {
        font-size: 24px;
        color: #ffffff;
        font-weight: bold;
    }
    """
