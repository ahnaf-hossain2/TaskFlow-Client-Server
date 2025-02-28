<<<<<<< HEAD
import sys
import json
import socket
import threading
import time
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget,
    QListWidget, QPushButton, QLabel, QSystemTrayIcon, QMessageBox, QMenu, QListWidgetItem,
    QTabWidget, QInputDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QCloseEvent, QAction

CLIENT_CONFIG_FILE = "client_config.json"

class ClientGUI(QMainWindow):

    update_signal = pyqtSignal(dict)  # Signal for UI updates
    notification_signal = pyqtSignal(dict)

    def __init__(self, server_host, server_port):
        super().__init__()
        self.server_host = server_host
        self.server_port = server_port
        self.client_id = self.load_client_id()  # Load client ID
        self.tasks = []
        self.notifications = []
        self.client_socket = None
        self.connected = False

        self.setWindowTitle(f"Task Manager - {self.client_id if self.client_id else 'Not Logged In'}")
        self.setGeometry(300, 300, 400, 300)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.setup_task_tab()
        self.setup_notification_tab()

        self.status_label = QLabel("Status: Disconnected")
        central_layout = QVBoxLayout()  # Layout for status label
        central_layout.addWidget(self.status_label)
        central_layout.addWidget(self.tabs)  # Add tabs to central layout

        central_widget = QWidget()
        central_widget.setLayout(central_layout)  # Set central layout
        self.setCentralWidget(central_widget)

        # --- Tray Icon Setup ---
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("C:\\Users\\User\\Desktop\\TaskManager\\icon.png"))  # Replace with your icon path
        self.tray_icon.setVisible(True)

        # Tray icon menu
        tray_menu = QMenu()
        show_hide_action = tray_menu.addAction("Show/Hide")
        exit_action = tray_menu.addAction("Exit")
        show_hide_action.triggered.connect(self.toggle_window_visibility)
        exit_action.triggered.connect(self.close_application)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        # --- End Tray Icon Setup ---

        self.update_signal.connect(self.update_ui)
        self.notification_signal.connect(self.handle_notification)

        # One-time login (if needed) and connection
        if not self.client_id:
            self.show_login_dialog()  # Show login only if no ID is saved
        else:
            self.connect_thread = threading.Thread(target=self.connect_to_server, daemon=True)
            self.connect_thread.start()

    def setup_task_tab(self):
        self.task_tab = QWidget()
        task_layout = QVBoxLayout(self.task_tab)
        self.task_list = QListWidget()
        task_layout.addWidget(QLabel("Tasks:"))
        task_layout.addWidget(self.task_list)
        self.complete_button = QPushButton("Mark as Completed/In Progress")
        self.complete_button.clicked.connect(self.mark_task_completed)
        task_layout.addWidget(self.complete_button)
        self.tabs.addTab(self.task_tab, "Tasks")

    def setup_notification_tab(self):
        self.notification_tab = QWidget()
        notification_layout = QVBoxLayout(self.notification_tab)
        self.notification_list = QListWidget()
        notification_layout.addWidget(QLabel("Notifications:"))
        notification_layout.addWidget(self.notification_list)
        self.tabs.addTab(self.notification_tab, "Notifications")

    def load_client_id(self):
        """Loads the client ID from the config file."""
        try:
            with open(CLIENT_CONFIG_FILE, "r") as file:
                config = json.load(file)
                return config.get("client_id")
        except FileNotFoundError:
            return None

    def save_client_id(self, client_id):
        """Saves the client ID to the config file."""
        config = {"client_id": client_id}
        with open(CLIENT_CONFIG_FILE, "w") as file:
            json.dump(config, file, indent=4)

    def show_login_dialog(self):
        """Shows a simple dialog to get the client ID."""
        while True:  # Keep asking until a valid ID is entered
            client_id, ok = QInputDialog.getText(self, "Login", "Enter your Client ID:")
            if ok and client_id.strip():
                self.client_id = client_id.strip()
                self.save_client_id(self.client_id)
                self.setWindowTitle(f"Task Manager - {self.client_id}")
                self.connect_thread = threading.Thread(target=self.connect_to_server, daemon=True)
                self.connect_thread.start()
                break
            elif ok:
                QMessageBox.warning(self, "Error", "Client ID cannot be empty.")
            else:
                sys.exit(0)

    def connect_to_server(self):
        while not self.connected:
            try:
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.settimeout(5)
                self.client_socket.connect((self.server_host, self.server_port))
                self.client_socket.settimeout(None)
                self.client_socket.send(self.client_id.encode("utf-8"))

                response = self.client_socket.recv(1024).decode("utf-8")
                if not response:
                    raise Exception("Connection closed by server")
                data = json.loads(response)

                if data.get("type") == "invalid_id":
                    self.status_label.setText("Status: Invalid Client ID")
                    self.client_socket.close()
                    QMessageBox.warning(self, "Error", "Invalid Client ID. Please contact the administrator.")
                    if os.path.exists(CLIENT_CONFIG_FILE):
                        os.remove(CLIENT_CONFIG_FILE)
                    self.client_id = None
                    self.show_login_dialog()
                    return
                elif data.get("type") == "client_removed":
                    self.status_label.setText("Status: Client Removed")
                    self.client_socket.close()
                    QMessageBox.warning(self, "Error", "Your client has been removed by the server.")
                    if os.path.exists(CLIENT_CONFIG_FILE):
                        os.remove(CLIENT_CONFIG_FILE)
                    self.client_id = None
                    self.show_login_dialog()
                    return

                self.connected = True
                self.status_label.setText("Status: Connected")
                self.listen_thread = threading.Thread(target=self.listen_for_updates, daemon=True)
                self.listen_thread.start()

            except socket.timeout:
                self.status_label.setText("Status: Connection timeout")
                QMessageBox.warning(self, "Connection Error", "Server is not responding. Please try again later.")
                time.sleep(5)
            except ConnectionRefusedError:
                self.status_label.setText("Status: Server not running")
                result = QMessageBox.warning(
                    self,
                    "Server Offline",
                    "The server is not running. Try again later?",
                    QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel
                )
                if result == QMessageBox.StandardButton.Cancel:
                    sys.exit(0)
                time.sleep(5)
            except Exception as e:
                print(f"Connection failed: {e}")
                self.status_label.setText("Status: Disconnected. Retrying...")
                time.sleep(5)

    def listen_for_updates(self):
        while self.connected:
            try:
                message = self.client_socket.recv(4096).decode("utf-8")
                if not message:
                    break
                data = json.loads(message)

                if data["type"] == "client_removed":
                    self.connected = False
                    self.status_label.setText("Status: Client Removed")
                    QMessageBox.warning(self, "Removed", "Your client has been removed by the server.")
                    if os.path.exists(CLIENT_CONFIG_FILE):
                        os.remove(CLIENT_CONFIG_FILE)
                    self.client_id = None
                    self.client_socket.close()
                    self.show_login_dialog()
                    break

                elif data["type"] == "delete_notification":
                    notification_id = data["data"]["id"]
                    self.notifications = [n for n in self.notifications if n["id"] != notification_id]
                    self.update_signal.emit({"type": "notifications", "data": self.notifications})

                elif data["type"] == "initial_notifications":
                    self.notifications = data["data"]
                    for notification in self.notifications:
                        self.notification_signal.emit(notification)

                elif data["type"] == "initial_tasks":  # ✅ FIX: Load tasks when client starts
                    self.tasks = data["data"]  # Store the tasks received from the server
                    self.update_signal.emit({"type": "tasks", "data": self.tasks})

                elif data["type"] == "new_task":
                    self.tasks.append(data["data"])
                    self.update_signal.emit({"type": "tasks", "data": self.tasks})
                    self.tray_icon.showMessage(
                        "New Task Assigned",
                        f"Task: {data['data']['description']}",
                        QSystemTrayIcon.MessageIcon.Information,
                        5000
                    )

                elif data["type"] == "task_update_admin":
                    for i, task in enumerate(self.tasks):
                        if i == data["data"]["task_id"]:
                            self.tasks[i] = {
                                "description": data["data"]["description"],
                                "due_date": data["data"]["due_date"],
                                "status": data["data"]["status"],
                            }
                            break
                    self.update_signal.emit({"type": "tasks", "data": self.tasks})

                elif data["type"] == "delete_task":
                    task_id_to_delete = data["data"]["task_id"]
                    if 0 <= task_id_to_delete < len(self.tasks):
                        del self.tasks[task_id_to_delete]
                        self.update_signal.emit({"type": "tasks", "data": self.tasks})

                elif data["type"] == "new_notification":
                    self.notifications.append(data["data"])
                    self.notification_signal.emit(data["data"])

            except (ConnectionResetError, BrokenPipeError, json.JSONDecodeError) as e:
                print(f"Server connection lost: {e}")
                self.connected = False
                self.status_label.setText("Status: Disconnected")
                self.client_socket.close()
                self.connect_to_server()
                break
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                break


    def update_ui(self, update_data):
        if update_data["type"] == "tasks":
            self.task_list.clear()
            for i, task in enumerate(update_data["data"]):
                item = QListWidgetItem(
                    f"Task {i}: {task['description']} (Due: {task['due_date']}, Status: {task['status']})"
                )
                item.setData(Qt.ItemDataRole.UserRole, i)
                self.task_list.addItem(item)
        elif update_data["type"] == "notifications":
            self.notification_list.clear()
            for notification in update_data["data"]:
                item = QListWidgetItem(f"{notification['message']} (Status: {notification['status']})")
                self.notification_list.addItem(item)

    def mark_task_completed(self):
        selected_item = self.task_list.currentItem()
        if selected_item:
            task_index = selected_item.data(Qt.ItemDataRole.UserRole)
            if 0 <= task_index < len(self.tasks):
                current_status = self.tasks[task_index]["status"]
                new_status = "Completed" if current_status != "Completed" else "In Progress"
                self.tasks[task_index]["status"] = new_status
                try:
                    update_message = json.dumps({"task_update": {"task_id": task_index, "status": new_status}})
                    self.client_socket.send(update_message.encode("utf-8"))
                    self.update_ui({"type": "tasks", "data": self.tasks})
                except Exception as e:
                    print(f"Error sending task update: {e}")
                    QMessageBox.critical(self, "Error", "Failed to send task update. Check server connection.")
            else:
                print(f"Invalid task index: {task_index}")

    def handle_notification(self, notification_data):
        message = notification_data["message"]
        # If the main window is not visible, show a modal popup
        if not self.isVisible():
            QMessageBox.information(self, "New Notification", message)
        else:
            self.tray_icon.showMessage(
                "New Notification",
                message,
                QSystemTrayIcon.MessageIcon.Information,
                5000  # Display for 5 seconds
            )
        # Update the notification list in the UI.
        self.update_ui({"type": "notifications", "data": self.notifications})
        # Mark the notification as read.
        try:
            read_message = json.dumps({"notification_read": notification_data["id"]})
            self.client_socket.send(read_message.encode("utf-8"))
        except Exception as e:
            print(f"Error sending notification read receipt: {e}")

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_window_visibility()

    def toggle_window_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.showNormal()
            self.activateWindow()

    def close_application(self):
        self.connected = False
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
        QApplication.quit()

    def closeEvent(self, event: QCloseEvent):
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "Running in Tray",
            "The application is still running. Use the tray icon to exit.",
            QSystemTrayIcon.MessageIcon.Information,
            3000
        )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    client = ClientGUI("127.0.0.1", 5000)  # Adjust host/port as needed
    client.show()
    sys.exit(app.exec())
=======
import sys
import json
import socket
import threading
import time
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget,
    QListWidget, QPushButton, QLabel, QSystemTrayIcon, QMessageBox, QMenu, QListWidgetItem,
    QTabWidget, QInputDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QCloseEvent, QAction

CLIENT_CONFIG_FILE = "client_config.json"

class ClientGUI(QMainWindow):

    update_signal = pyqtSignal(dict)  # Signal for UI updates
    notification_signal = pyqtSignal(dict)

    def __init__(self, server_host, server_port):
        super().__init__()
        self.server_host = server_host
        self.server_port = server_port
        self.client_id = self.load_client_id()  # Load client ID
        self.tasks = []
        self.notifications = []
        self.client_socket = None
        self.connected = False

        self.setWindowTitle(f"Task Manager - {self.client_id if self.client_id else 'Not Logged In'}")
        self.setGeometry(300, 300, 400, 300)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.setup_task_tab()
        self.setup_notification_tab()

        self.status_label = QLabel("Status: Disconnected")
        central_layout = QVBoxLayout()  # Layout for status label
        central_layout.addWidget(self.status_label)
        central_layout.addWidget(self.tabs)  # Add tabs to central layout

        central_widget = QWidget()
        central_widget.setLayout(central_layout)  # Set central layout
        self.setCentralWidget(central_widget)

        # --- Tray Icon Setup ---
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("C:\\Users\\User\\Desktop\\TaskManager\\icon.png"))  # Replace with your icon path
        self.tray_icon.setVisible(True)

        # Tray icon menu
        tray_menu = QMenu()
        show_hide_action = tray_menu.addAction("Show/Hide")
        exit_action = tray_menu.addAction("Exit")
        show_hide_action.triggered.connect(self.toggle_window_visibility)
        exit_action.triggered.connect(self.close_application)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        # --- End Tray Icon Setup ---

        self.update_signal.connect(self.update_ui)
        self.notification_signal.connect(self.handle_notification)

        # One-time login (if needed) and connection
        if not self.client_id:
            self.show_login_dialog()  # Show login only if no ID is saved
        else:
            self.connect_thread = threading.Thread(target=self.connect_to_server, daemon=True)
            self.connect_thread.start()

    def setup_task_tab(self):
        self.task_tab = QWidget()
        task_layout = QVBoxLayout(self.task_tab)
        self.task_list = QListWidget()
        task_layout.addWidget(QLabel("Tasks:"))
        task_layout.addWidget(self.task_list)
        self.complete_button = QPushButton("Mark as Completed/In Progress")
        self.complete_button.clicked.connect(self.mark_task_completed)
        task_layout.addWidget(self.complete_button)
        self.tabs.addTab(self.task_tab, "Tasks")

    def setup_notification_tab(self):
        self.notification_tab = QWidget()
        notification_layout = QVBoxLayout(self.notification_tab)
        self.notification_list = QListWidget()
        notification_layout.addWidget(QLabel("Notifications:"))
        notification_layout.addWidget(self.notification_list)
        self.tabs.addTab(self.notification_tab, "Notifications")

    def load_client_id(self):
        """Loads the client ID from the config file."""
        try:
            with open(CLIENT_CONFIG_FILE, "r") as file:
                config = json.load(file)
                return config.get("client_id")
        except FileNotFoundError:
            return None

    def save_client_id(self, client_id):
        """Saves the client ID to the config file."""
        config = {"client_id": client_id}
        with open(CLIENT_CONFIG_FILE, "w") as file:
            json.dump(config, file, indent=4)

    def show_login_dialog(self):
        """Shows a simple dialog to get the client ID."""
        while True:  # Keep asking until a valid ID is entered
            client_id, ok = QInputDialog.getText(self, "Login", "Enter your Client ID:")
            if ok and client_id.strip():
                self.client_id = client_id.strip()
                self.save_client_id(self.client_id)
                self.setWindowTitle(f"Task Manager - {self.client_id}")
                self.connect_thread = threading.Thread(target=self.connect_to_server, daemon=True)
                self.connect_thread.start()
                break
            elif ok:
                QMessageBox.warning(self, "Error", "Client ID cannot be empty.")
            else:
                sys.exit(0)

    def connect_to_server(self):
        while not self.connected:
            try:
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.settimeout(5)
                self.client_socket.connect((self.server_host, self.server_port))
                self.client_socket.settimeout(None)
                self.client_socket.send(self.client_id.encode("utf-8"))

                response = self.client_socket.recv(1024).decode("utf-8")
                if not response:
                    raise Exception("Connection closed by server")
                data = json.loads(response)

                if data.get("type") == "invalid_id":
                    self.status_label.setText("Status: Invalid Client ID")
                    self.client_socket.close()
                    QMessageBox.warning(self, "Error", "Invalid Client ID. Please contact the administrator.")
                    if os.path.exists(CLIENT_CONFIG_FILE):
                        os.remove(CLIENT_CONFIG_FILE)
                    self.client_id = None
                    self.show_login_dialog()
                    return
                elif data.get("type") == "client_removed":
                    self.status_label.setText("Status: Client Removed")
                    self.client_socket.close()
                    QMessageBox.warning(self, "Error", "Your client has been removed by the server.")
                    if os.path.exists(CLIENT_CONFIG_FILE):
                        os.remove(CLIENT_CONFIG_FILE)
                    self.client_id = None
                    self.show_login_dialog()
                    return

                self.connected = True
                self.status_label.setText("Status: Connected")
                self.listen_thread = threading.Thread(target=self.listen_for_updates, daemon=True)
                self.listen_thread.start()

            except socket.timeout:
                self.status_label.setText("Status: Connection timeout")
                QMessageBox.warning(self, "Connection Error", "Server is not responding. Please try again later.")
                time.sleep(5)
            except ConnectionRefusedError:
                self.status_label.setText("Status: Server not running")
                result = QMessageBox.warning(
                    self,
                    "Server Offline",
                    "The server is not running. Try again later?",
                    QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel
                )
                if result == QMessageBox.StandardButton.Cancel:
                    sys.exit(0)
                time.sleep(5)
            except Exception as e:
                print(f"Connection failed: {e}")
                self.status_label.setText("Status: Disconnected. Retrying...")
                time.sleep(5)

    def listen_for_updates(self):
        while self.connected:
            try:
                message = self.client_socket.recv(4096).decode("utf-8")
                if not message:
                    break
                data = json.loads(message)

                if data["type"] == "client_removed":
                    self.connected = False
                    self.status_label.setText("Status: Client Removed")
                    QMessageBox.warning(self, "Removed", "Your client has been removed by the server.")
                    if os.path.exists(CLIENT_CONFIG_FILE):
                        os.remove(CLIENT_CONFIG_FILE)
                    self.client_id = None
                    self.client_socket.close()
                    self.show_login_dialog()
                    break

                elif data["type"] == "delete_notification":
                    notification_id = data["data"]["id"]
                    self.notifications = [n for n in self.notifications if n["id"] != notification_id]
                    self.update_signal.emit({"type": "notifications", "data": self.notifications})

                elif data["type"] == "initial_notifications":
                    self.notifications = data["data"]
                    for notification in self.notifications:
                        self.notification_signal.emit(notification)
                elif data["type"] == "new_task":
                    self.tasks.append(data["data"])
                    self.update_signal.emit({"type": "tasks", "data": self.tasks})
                    self.tray_icon.showMessage(
                        "New Task Assigned",
                        f"Task: {data['data']['description']}",
                        QSystemTrayIcon.MessageIcon.Information,
                        5000
                    )
                elif data["type"] == "task_update_admin":
                    for i, task in enumerate(self.tasks):
                        if i == data["data"]["task_id"]:
                            self.tasks[i] = {
                                "description": data["data"]["description"],
                                "due_date": data["data"]["due_date"],
                                "status": data["data"]["status"],
                            }
                            break
                    self.update_signal.emit({"type": "tasks", "data": self.tasks})
                elif data["type"] == "delete_task":
                    task_id_to_delete = data["data"]["task_id"]
                    if 0 <= task_id_to_delete < len(self.tasks):
                        del self.tasks[task_id_to_delete]
                        self.update_signal.emit({"type": "tasks", "data": self.tasks})
                elif data["type"] == "new_notification":
                    self.notifications.append(data["data"])
                    self.notification_signal.emit(data["data"])

            except (ConnectionResetError, BrokenPipeError, json.JSONDecodeError) as e:
                print(f"Server connection lost: {e}")
                self.connected = False
                self.status_label.setText("Status: Disconnected")
                self.client_socket.close()
                self.connect_to_server()
                break
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                break

    def update_ui(self, update_data):
        if update_data["type"] == "tasks":
            self.task_list.clear()
            for i, task in enumerate(update_data["data"]):
                item = QListWidgetItem(
                    f"Task {i}: {task['description']} (Due: {task['due_date']}, Status: {task['status']})"
                )
                item.setData(Qt.ItemDataRole.UserRole, i)
                self.task_list.addItem(item)
        elif update_data["type"] == "notifications":
            self.notification_list.clear()
            for notification in update_data["data"]:
                item = QListWidgetItem(f"{notification['message']} (Status: {notification['status']})")
                self.notification_list.addItem(item)

    def mark_task_completed(self):
        selected_item = self.task_list.currentItem()
        if selected_item:
            task_index = selected_item.data(Qt.ItemDataRole.UserRole)
            if 0 <= task_index < len(self.tasks):
                current_status = self.tasks[task_index]["status"]
                new_status = "Completed" if current_status != "Completed" else "In Progress"
                self.tasks[task_index]["status"] = new_status
                try:
                    update_message = json.dumps({"task_update": {"task_id": task_index, "status": new_status}})
                    self.client_socket.send(update_message.encode("utf-8"))
                    self.update_ui({"type": "tasks", "data": self.tasks})
                except Exception as e:
                    print(f"Error sending task update: {e}")
                    QMessageBox.critical(self, "Error", "Failed to send task update. Check server connection.")
            else:
                print(f"Invalid task index: {task_index}")

    def handle_notification(self, notification_data):
        message = notification_data["message"]
        # If the main window is not visible, show a modal popup
        if not self.isVisible():
            QMessageBox.information(self, "New Notification", message)
        else:
            self.tray_icon.showMessage(
                "New Notification",
                message,
                QSystemTrayIcon.MessageIcon.Information,
                5000  # Display for 5 seconds
            )
        # Update the notification list in the UI.
        self.update_ui({"type": "notifications", "data": self.notifications})
        # Mark the notification as read.
        try:
            read_message = json.dumps({"notification_read": notification_data["id"]})
            self.client_socket.send(read_message.encode("utf-8"))
        except Exception as e:
            print(f"Error sending notification read receipt: {e}")

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_window_visibility()

    def toggle_window_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.showNormal()
            self.activateWindow()

    def close_application(self):
        self.connected = False
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
        QApplication.quit()

    def closeEvent(self, event: QCloseEvent):
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "Running in Tray",
            "The application is still running. Use the tray icon to exit.",
            QSystemTrayIcon.MessageIcon.Information,
            3000
        )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    client = ClientGUI("127.0.0.1", 5000)  # Adjust host/port as needed
    client.show()
    sys.exit(app.exec())
>>>>>>> 6626719ed7e25982c59259da828b1a273912b6a0
