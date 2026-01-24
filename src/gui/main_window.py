import sys
import time
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QLabel, QListWidget, 
                               QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit, QMessageBox, QCheckBox)
from PySide6.QtCore import Qt, Signal, QThread, Slot, QObject

# Add src to path if needed (though main.py handles it, keeping it safe)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from src.core.zsxq_api import ZSXQCore

class BrowserWorker(QObject):
    """
    Worker object that lives in a separate thread and manages all Playwright interactions.
    """
    # Signals to UI
    log_msg = Signal(str)
    error_msg = Signal(str)
    browser_ready = Signal()
    login_status_result = Signal(bool)
    subscriptions_ready = Signal(list)
    files_list_ready = Signal(list)
    file_download_result = Signal(bool, str) # success, filename
    
    # Internal signals for queuing tasks
    _do_init = Signal()
    _do_check_login = Signal()
    _do_get_subs = Signal()
    _do_enter_planet = Signal(dict)
    _do_get_files = Signal()
    _do_download = Signal(dict)
    _do_stop = Signal()
    
    def __init__(self):
        super().__init__()
        self.core = None
        
        # Connect internal signals to slots
        self._do_init.connect(self._init_browser_impl)
        self._do_check_login.connect(self._check_login_impl)
        self._do_get_subs.connect(self._get_subscriptions_impl)
        self._do_enter_planet.connect(self._enter_planet_impl)
        self._do_get_files.connect(self._get_files_impl)
        self._do_download.connect(self._download_file_impl)
        self._do_stop.connect(self._stop_impl)

    @Slot()
    def init_browser(self):
        self._do_init.emit()

    @Slot()
    def _init_browser_impl(self):
        """Initialize and start the browser"""
        try:
            self.log_msg.emit("正在初始化核心模块...")
            self.core = ZSXQCore(
                download_dir="./downloads",
                user_data_dir="./browser_data/zsxq"
            )
            self.log_msg.emit("正在启动浏览器...")
            self.core.start_browser(headless=False)
            self.log_msg.emit("浏览器启动成功")
            self.browser_ready.emit()
            
            # Auto-check login after start
            self.check_login()
        except Exception as e:
            self.error_msg.emit(f"启动失败: {str(e)}")

    @Slot()
    def check_login(self):
        self._do_check_login.emit()

    @Slot()
    def _check_login_impl(self):
        """Check login status"""
        if not self.core: return
        try:
            self.log_msg.emit("检查登录状态...")
            is_logged_in = self.core.check_login_status()
            self.login_status_result.emit(is_logged_in)
            if is_logged_in:
                self.log_msg.emit("已登录")
                self.get_subscriptions()
            else:
                self.log_msg.emit("未登录，请手动登录")
        except Exception as e:
            self.error_msg.emit(str(e))

    @Slot()
    def get_subscriptions(self):
        self._do_get_subs.emit()

    @Slot()
    def _get_subscriptions_impl(self):
        """Fetch subscriptions"""
        if not self.core: return
        try:
            self.log_msg.emit("正在获取星球列表...")
            subs = self.core.get_subscriptions(scroll_attempts=2)
            self.subscriptions_ready.emit(subs)
            self.log_msg.emit(f"获取到 {len(subs)} 个星球")
        except Exception as e:
            self.error_msg.emit(f"获取订阅失败: {str(e)}")

    @Slot(dict)
    def enter_planet(self, sub):
        self._do_enter_planet.emit(sub)

    @Slot(dict)
    def _enter_planet_impl(self, sub):
        """Enter a specific planet"""
        if not self.core: return
        try:
            name = sub.get('name', 'Unknown')
            self.log_msg.emit(f"正在进入星球: {name}")
            self.core.open_subscription(sub)
            self.log_msg.emit("进入星球页面，尝试查找文件入口...")
            self.core.enter_files_section()
            self.log_msg.emit("已进入文件列表页面")
            
            # Auto load files
            self.get_files()
        except Exception as e:
            self.error_msg.emit(f"进入星球失败: {str(e)}")

    @Slot()
    def get_files(self):
        self._do_get_files.emit()

    @Slot()
    def _get_files_impl(self):
        """Load files list"""
        if not self.core: return
        try:
            self.log_msg.emit("正在扫描文件列表 (滚动加载)...")
            # Callback for progress could be added here
            files = self.core.get_files_list(scroll_attempts=5)
            self.files_list_ready.emit(files)
            self.log_msg.emit(f"扫描完成，共找到 {len(files)} 个文件")
        except Exception as e:
            self.error_msg.emit(f"扫描文件失败: {str(e)}")

    @Slot(dict)
    def download_file(self, file_obj):
        self._do_download.emit(file_obj)

    @Slot(dict)
    def _download_file_impl(self, file_obj):
        """Download a single file"""
        if not self.core: return
        try:
            name = file_obj.get('fileName', 'Unknown')
            self.log_msg.emit(f"开始下载: {name}")
            success = self.core.download_single_file(file_obj)
            self.file_download_result.emit(success, name)
            if success:
                self.log_msg.emit(f"下载成功: {name}")
            else:
                self.error_msg.emit(f"下载失败: {name}")
        except Exception as e:
            self.error_msg.emit(f"下载异常: {str(e)}")

    @Slot()
    def stop(self):
        self._do_stop.emit()

    @Slot()
    def _stop_impl(self):
        """Cleanup"""
        if self.core:
            self.core.close()

class WorkerThread(QThread):
    def run(self):
        self.exec()

class MainWindow(QMainWindow):
    # Signals to request actions from worker
    sig_init = Signal()
    sig_check_login = Signal()
    sig_get_subs = Signal()
    sig_enter_planet = Signal(dict)
    sig_get_files = Signal()
    sig_download = Signal(dict)
    sig_stop = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("知识星球下载器 (ZSXQ Downloader) - Phase 1")
        self.resize(1000, 700)
        
        self.setup_ui()
        self.setup_worker()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Left Panel
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("已订阅星球:"))
        self.subs_list = QListWidget()
        self.subs_list.itemClicked.connect(self.on_sub_selected)
        left_layout.addWidget(self.subs_list)
        
        btn_refresh = QPushButton("刷新列表")
        btn_refresh.clicked.connect(lambda: self.sig_get_subs.emit())
        left_layout.addWidget(btn_refresh)
        
        main_layout.addLayout(left_layout, 1)

        # Right Panel
        right_layout = QVBoxLayout()
        
        # Status Bar
        status_layout = QHBoxLayout()
        self.lbl_status = QLabel("状态: 等待初始化...")
        status_layout.addWidget(self.lbl_status)
        btn_login = QPushButton("手动检测登录")
        btn_login.clicked.connect(lambda: self.sig_check_login.emit())
        status_layout.addWidget(btn_login)
        right_layout.addLayout(status_layout)

        # Files Table
        right_layout.addWidget(QLabel("文件列表:"))
        self.files_table = QTableWidget()
        self.files_table.setColumnCount(4)
        self.files_table.setHorizontalHeaderLabels(["选择", "文件名", "状态", "操作"])
        self.files_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.files_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        right_layout.addWidget(self.files_table)

        # Actions
        actions_layout = QHBoxLayout()
        
        btn_select_all = QPushButton("全选")
        btn_select_all.clicked.connect(self.select_all_files)
        actions_layout.addWidget(btn_select_all)

        btn_download_batch = QPushButton("批量下载选中")
        btn_download_batch.clicked.connect(self.download_selected_files)
        actions_layout.addWidget(btn_download_batch)

        btn_load = QPushButton("加载更多文件")
        btn_load.clicked.connect(lambda: self.sig_get_files.emit())
        actions_layout.addWidget(btn_load)
        right_layout.addLayout(actions_layout)

        # Logs
        right_layout.addWidget(QLabel("日志:"))
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(150)
        right_layout.addWidget(self.log_area)

        main_layout.addLayout(right_layout, 3)

    def setup_worker(self):
        self.thread = WorkerThread()
        self.worker = BrowserWorker()
        self.worker.moveToThread(self.thread)

        # Connect Worker signals to UI slots
        self.worker.log_msg.connect(self.log)
        self.worker.error_msg.connect(self.on_error)
        self.worker.browser_ready.connect(self.on_browser_ready)
        self.worker.login_status_result.connect(self.on_login_status)
        self.worker.subscriptions_ready.connect(self.on_subscriptions_ready)
        self.worker.files_list_ready.connect(self.on_files_ready)
        self.worker.file_download_result.connect(self.on_download_result)

        # Connect UI signals to Worker slots
        self.sig_init.connect(self.worker.init_browser)
        self.sig_check_login.connect(self.worker.check_login)
        self.sig_get_subs.connect(self.worker.get_subscriptions)
        self.sig_enter_planet.connect(self.worker.enter_planet)
        self.sig_get_files.connect(self.worker.get_files)
        self.sig_download.connect(self.worker.download_file)
        self.sig_stop.connect(self.worker.stop)

        # Start thread
        self.thread.start()
        
        # Trigger init
        self.sig_init.emit()

    def log(self, msg):
        timestamp = time.strftime('%H:%M:%S')
        self.log_area.append(f"[{timestamp}] {msg}")
        # Scroll to bottom
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())

    def on_error(self, msg):
        self.log(f"ERROR: {msg}")
        QMessageBox.warning(self, "错误", msg)

    def on_browser_ready(self):
        self.lbl_status.setText("状态: 浏览器就绪")

    def on_login_status(self, logged_in):
        self.lbl_status.setText(f"状态: {'已登录' if logged_in else '未登录'}")
        if not logged_in:
            QMessageBox.information(self, "需登录", "请在弹出的浏览器中登录，完成后点击'手动检测登录'")

    def on_subscriptions_ready(self, subs):
        self.subs_list.clear()
        self.current_subs = subs
        for sub in subs:
            self.subs_list.addItem(sub.get('name', 'Unknown'))

    def on_sub_selected(self, item):
        name = item.text()
        sub = next((s for s in self.current_subs if s.get('name') == name), None)
        if sub:
            self.sig_enter_planet.emit(sub)

    def on_files_ready(self, files):
        self.files_table.setRowCount(len(files))
        download_dir = os.path.abspath("./downloads")
        import re
        
        # Store current files data
        self.current_files_data = files

        for i, f in enumerate(files):
            filename = f.get('fileName', 'Unknown')
            
            # Checkbox
            chk = QCheckBox()
            widget = QWidget()
            layout = QHBoxLayout(widget)
            layout.addWidget(chk)
            layout.setAlignment(Qt.AlignCenter)
            layout.setContentsMargins(0,0,0,0)
            self.files_table.setCellWidget(i, 0, widget)

            self.files_table.setItem(i, 1, QTableWidgetItem(filename))
            
            # Check if file already exists locally
            clean_name = re.sub(r'[\\/*?:"<>|]', "", filename)
            file_path = os.path.join(download_dir, clean_name)
            
            is_downloaded = os.path.exists(file_path) and os.path.getsize(file_path) > 0
            
            if is_downloaded:
                chk.setEnabled(False) # Disable selection for downloaded files
                self.files_table.setItem(i, 2, QTableWidgetItem("已下载"))
                btn = QPushButton("打开位置")
                btn.clicked.connect(lambda checked, fn=filename: self.open_download_folder(fn))
                self.files_table.setCellWidget(i, 3, btn)
            else:
                self.files_table.setItem(i, 2, QTableWidgetItem("未下载"))
                btn = QPushButton("下载")
                # Correct closure capture
                btn.clicked.connect(lambda checked, f=f: self.sig_download.emit(f))
                self.files_table.setCellWidget(i, 3, btn)

    def select_all_files(self):
        """Select all undownloaded files"""
        for row in range(self.files_table.rowCount()):
            widget = self.files_table.cellWidget(row, 0)
            if widget:
                chk = widget.findChild(QCheckBox)
                if chk and chk.isEnabled():
                    chk.setChecked(True)

    def download_selected_files(self):
        """Download all checked files"""
        count = 0
        for row in range(self.files_table.rowCount()):
            widget = self.files_table.cellWidget(row, 0)
            if widget:
                chk = widget.findChild(QCheckBox)
                if chk and chk.isChecked() and chk.isEnabled():
                    # Find file data
                    filename = self.files_table.item(row, 1).text()
                    file_obj = next((f for f in self.current_files_data if f.get('fileName') == filename), None)
                    if file_obj:
                        self.sig_download.emit(file_obj)
                        count += 1
                        # Uncheck to prevent double download
                        chk.setChecked(False)
                        chk.setEnabled(False)
                        self.files_table.setItem(row, 2, QTableWidgetItem("等待下载..."))
        
        if count > 0:
            self.log(f"已将 {count} 个文件加入下载队列")
        else:
            QMessageBox.information(self, "提示", "请先选择需要下载的文件")

    def on_download_result(self, success, filename):
        # Update status in table (simple scan)
        for row in range(self.files_table.rowCount()):
            item = self.files_table.item(row, 1) # Filename is now col 1
            if item and item.text() == filename:
                status = "下载成功" if success else "失败"
                self.files_table.setItem(row, 2, QTableWidgetItem(status))
                
                if success:
                    # 将下载按钮改为"打开位置"
                    btn = QPushButton("打开位置")
                    btn.clicked.connect(lambda: self.open_download_folder(filename))
                    self.files_table.setCellWidget(row, 3, btn)
                    
                    # Update checkbox
                    widget = self.files_table.cellWidget(row, 0)
                    if widget:
                        chk = widget.findChild(QCheckBox)
                        if chk: 
                            chk.setEnabled(False)
                            chk.setChecked(False)
                break

    def open_download_folder(self, filename):
        """Open the folder containing the downloaded file and select it"""
        # 假设下载目录在 ./downloads
        download_dir = os.path.abspath("./downloads")
        # 移除非法字符以匹配保存时的逻辑
        import re
        clean_name = re.sub(r'[\\/*?:"<>|]', "", filename)
        file_path = os.path.join(download_dir, clean_name)
        
        if os.path.exists(file_path):
            if sys.platform == 'win32':
                os.system(f'explorer /select,"{file_path}"')
            elif sys.platform == 'darwin':
                os.system(f'open -R "{file_path}"')
            else:
                # Linux usually
                os.system(f'xdg-open "{os.path.dirname(file_path)}"')
        else:
            QMessageBox.warning(self, "文件不存在", f"找不到文件: {file_path}")

    def closeEvent(self, event):
        self.sig_stop.emit()
        self.thread.quit()
        self.thread.wait(2000)
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
