import sys
import json
import socket
import threading
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget,
    QTextEdit, QTableWidget, QTableWidgetItem, QComboBox, QMessageBox,
    QLineEdit, QTabWidget, QHBoxLayout, QDialog, QFormLayout
)
from PyQt6.QtCore import Qt, QDateTime, QTimer
from PyQt6.QtGui import QAction, QIcon

# --- Server & Admin Panel Configuration ---
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
CONFIG_FILE = "server_config.json"

clients = {}
tasks = {}
client_data = {}
notifications = []
next_notification_id = 1


def load_server_config():
    """Loads server IP and port from config file or defaults."""
    try:
        with open(CONFIG_FILE, "r") as file:
            config = json.load(file)
            return config["host"], config["port"]
    except FileNotFoundError:
        return DEFAULT_HOST, DEFAULT_PORT

def save_server_config(host, port):
    """Saves server IP and port to config file."""
    config = {"host": host, "port": port}
    with open(CONFIG_FILE, "w") as file:
        json.dump(config, file, indent=4)

def load_data():
    global client_data, tasks, notifications, next_notification_id
    try:
        with open("clients.json", "r") as file:
            client_data = json.load(file)
    except FileNotFoundError:
        client_data = {}
    try:
        with open("tasks.json", "r") as file:
            tasks = json.load(file)
    except FileNotFoundError:
        tasks = {}
    try:
        with open("notifications.json", "r") as file:
            notifications = json.load(file)
            if notifications:
                next_notification_id = max(n["id"] for n in notifications) + 1
    except FileNotFoundError:
        notifications = []



def save_data():
    with open("clients.json", "w") as file:
        json.dump(client_data, file, indent=4)
    with open("tasks.json", "w") as file:
        json.dump(tasks, file, indent=4)
    with open("notifications.json", "w") as file:
        json.dump(notifications, file, indent=4)

def send_update_to_client(client_id, update_type, data):
    """Sends an update to a specific client."""
    if client_id in clients:
        try:
            message = json.dumps({"type": update_type, "data": data})
            clients[client_id].send(message.encode("utf-8"))
        except Exception as e:
            print(f"Error sending update to {client_id}: {e}")
            remove_client_connection(client_id)
    window.handle_client_update(update_type, data)  # Notify the admin panel of the update

def remove_client_connection(client_id):
    """Safely removes a client's connection."""
    if client_id in clients:
        try:
            clients[client_id].close()
        except:
            pass
        del clients[client_id]
        print(f"Client {client_id} disconnected.")

def handle_client(client_socket, client_address):
    """Handles communication with a connected client."""
    global next_notification_id
    try:
        client_id = client_socket.recv(1024).decode("utf-8")
        if client_id not in client_data:
            # Send invalid ID message before closing
            error_msg = json.dumps({"type": "invalid_id"})
            client_socket.send(error_msg.encode("utf-8"))
            client_socket.close()
            return

        clients[client_id] = client_socket
        print(f"Client {client_id} connected from {client_address}")

        # Send initial tasks and unread notifications
        client_tasks = tasks.get(client_id, [])
        print(f"Sending tasks to {client_id}: {client_tasks}")  # ✅ Debugging line
        send_update_to_client(client_id, "initial_tasks", client_tasks)

        unread_notifications = [n for n in notifications if n["client_id"] in (client_id, "ALL") and n["status"] == "unread"]
        send_update_to_client(client_id, "initial_notifications", unread_notifications)


        clients[client_id] = client_socket
        print(f"Client {client_id} connected from {client_address}")

        # Send initial tasks and unread notifications
        send_update_to_client(client_id, "initial_tasks", tasks.get(client_id, []))
        unread_notifications = [n for n in notifications if n["client_id"] in (client_id, "ALL") and n["status"] == "unread"]
        send_update_to_client(client_id, "initial_notifications", unread_notifications)

        while True:
            try:
                message = client_socket.recv(1024).decode("utf-8")
                if not message:
                    break
                data = json.loads(message)

                if "task_update" in data:
                    task_update = data["task_update"]
                    task_id = task_update["task_id"]  # Now expecting a *task_id*
                    status = task_update["status"]
                    if client_id in tasks and 0 <= task_id < len(tasks[client_id]):
                        tasks[client_id][task_id]["status"] = status
                        save_data()
                        print(f"Task {task_id} for client {client_id} updated to {status}")

                elif "notification_read" in data:
                    notification_id = data["notification_read"]
                    for notification in notifications:
                        if notification["client_id"] == client_id and notification["id"] == notification_id:
                            notification["status"] = "read"
                            notification["read_timestamp"] = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
                            save_data()
                            break # Stop searching after the first matching ID.
            except (json.JSONDecodeError, ConnectionResetError, BrokenPipeError) as e:
                print(f"Client {client_id} error: {e}")
                break
            except Exception as e:
                print(f"Unexpected error with client {client_id}: {e}")
                break

    except Exception as e:
        print(f"Error during client setup: {e}")
    finally:
         remove_client_connection(client_id)


def start_server(host, port):
    """Starts the TCP server."""
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((host, port))
        server.listen(5)
        print(f"Server listening on {host}:{port}")
        while True:
            try:
                client_socket, client_address = server.accept()
                threading.Thread(target=handle_client, args=(client_socket, client_address)).start()
            except Exception as e:
                print(f"Error accepting connection: {e}")
    except Exception as e:
        print(f"Failed to start server: {e}")
        sys.exit(1)



class ServerConfigDialog(QDialog):
    """Dialog for initial server configuration."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Server Configuration")
        self.host_input = QLineEdit(DEFAULT_HOST)
        self.port_input = QLineEdit(str(DEFAULT_PORT))
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)

        layout = QFormLayout()
        layout.addRow("Server IP:", self.host_input)
        layout.addRow("Server Port:", self.port_input)
        layout.addRow(self.ok_button)
        self.setLayout(layout)

    def get_config(self):
        return self.host_input.text(), int(self.port_input.text())



class AdminPanel(QMainWindow):
    def __init__(self, host, port):
        super().__init__()
        self.host = host  # Store host and port
        self.port = port
        self.setWindowTitle("Task Management System - Admin")
        self.setGeometry(200, 200, 800, 600)
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.setup_clients_tab()
        self.setup_tasks_tab()
        self.setup_notifications_tab()
        self.load_existing_data()  # Load data *after* setting up the tabs

    def setup_clients_tab(self):
        self.clients_tab = QWidget()
        layout = QVBoxLayout()
        self.client_table = QTableWidget()
        self.client_table.setColumnCount(3)
        self.client_table.setHorizontalHeaderLabels(["Client ID", "Client IP", "Client Name"])
        self.client_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked)
        self.client_table.cellChanged.connect(self.update_client_in_json)
        self.client_id_input = QLineEdit()
        self.client_ip_input = QLineEdit()
        self.client_name_input = QLineEdit()
        self.add_client_button = QPushButton("Add Client")
        self.remove_client_button = QPushButton("Remove Client")
        layout.addWidget(QLabel("Clients:"))
        layout.addWidget(self.client_table)
        layout.addWidget(QLabel("Client ID:"))
        layout.addWidget(self.client_id_input)
        layout.addWidget(QLabel("Client IP:"))
        layout.addWidget(self.client_ip_input)
        layout.addWidget(QLabel("Client Name:"))
        layout.addWidget(self.client_name_input)
        layout.addWidget(self.add_client_button)
        layout.addWidget(self.remove_client_button)
        self.clients_tab.setLayout(layout)
        self.tabs.addTab(self.clients_tab, "Clients")
        self.add_client_button.clicked.connect(self.add_client)
        self.remove_client_button.clicked.connect(self.remove_client)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_all_tabs)
        self.refresh_timer.start(5000)  # Refresh every 5 seconds

    def add_client(self):
        client_id = self.client_id_input.text().strip()
        client_ip = self.client_ip_input.text().strip()
        client_name = self.client_name_input.text().strip()
        if client_id and client_ip and client_name:
            if client_id not in client_data:
                client_data[client_id] = {"ip": client_ip, "name": client_name}
                save_data()
                self.refresh_client_table()
                self.update_client_filter()  # Update the filters *after* adding a client
            else:
                QMessageBox.warning(self, "Error", "Client ID already exists!")
        else:
           QMessageBox.warning(self, "Error", "Please fill all client information!")
        self.client_id_input.clear()
        self.client_ip_input.clear()
        self.client_name_input.clear()

    def remove_client(self):
        selected_row = self.client_table.currentRow()
        if selected_row >= 0:
            client_id = self.client_table.item(selected_row, 0).text()
            confirm = QMessageBox.question(self, "Confirm Removal", f"Are you sure you want to remove client {client_id}?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if confirm == QMessageBox.StandardButton.Yes:
                if client_id in clients:
                    remove_client_connection(client_id)  # Close socket
                del client_data[client_id]
                if client_id in tasks:  # Remove associated tasks
                    del tasks[client_id]
                save_data()
                self.refresh_client_table()
                self.update_client_filter()  # Update filters after removing
                self.refresh_task_table()

        else:
            QMessageBox.warning(self, "Error", "Please select a client to remove!")

    def update_client_in_json(self, row, column):
        try:
            client_id = self.client_table.item(row, 0).text()
            if client_id in client_data:
                if column == 1:  # Client IP
                    client_data[client_id]["ip"] = self.client_table.item(row, column).text()
                elif column == 2:  # Client Name
                    client_data[client_id]["name"] = self.client_table.item(row, column).text()
                save_data()
        except Exception as e:
            QMessageBox.critical(self,"Error", f"Failed to update the client: {e}")

    def refresh_client_table(self):
        try:
            self.client_table.setRowCount(0)
            for client_id, info in client_data.items():
                row_position = self.client_table.rowCount()
                self.client_table.insertRow(row_position)
                self.client_table.setItem(row_position, 0, QTableWidgetItem(client_id))
                self.client_table.setItem(row_position, 1, QTableWidgetItem(info["ip"]))
                self.client_table.setItem(row_position, 2, QTableWidgetItem(info["name"]))
        except Exception as e:
             QMessageBox.critical(self,"Error", f"Failed to refresh client table: {e}")

    def setup_tasks_tab(self):
        self.tasks_tab = QWidget()
        layout = QVBoxLayout()

        # Filters
        filter_layout = QHBoxLayout()
        self.client_filter = QComboBox()
        self.date_order_filter = QComboBox()
        self.date_order_filter.addItems(["Ascending", "Descending"])
        self.filter_button = QPushButton("Filter Tasks")
        filter_layout.addWidget(QLabel("Filter by Client:"))
        filter_layout.addWidget(self.client_filter)
        filter_layout.addWidget(QLabel("Sort by Due Date:"))
        filter_layout.addWidget(self.date_order_filter)
        filter_layout.addWidget(self.filter_button)

        # Task Table
        self.task_table = QTableWidget()
        self.task_table.setColumnCount(4)
        self.task_table.setHorizontalHeaderLabels(["Client ID", "Task", "Due Date", "Status"])
        self.task_table.setMinimumHeight(150)
        self.task_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked)
        self.task_table.cellChanged.connect(self.update_task_in_json)

        # Task Input Fields
        self.task_input = QTextEdit()
        self.client_selector = QComboBox()  # Created *before* update_client_filter
        self.due_date_input = QLineEdit()
        self.add_task_button = QPushButton("Assign Task")
        self.status_selector = QComboBox()
        self.status_selector.addItems(["Pending", "In Progress", "Completed"])
        self.update_status_button = QPushButton("Update Status")
        self.delete_task_button = QPushButton("Delete Task")

        # Layout
        layout.addLayout(filter_layout)
        layout.addWidget(QLabel("Tasks:"))
        layout.addWidget(self.task_table)
        layout.addWidget(QLabel("New Task:"))
        layout.addWidget(self.task_input)
        layout.addWidget(QLabel("Assign to:"))
        layout.addWidget(self.client_selector)
        layout.addWidget(QLabel("Due Date (YYYY-MM-DD):"))
        layout.addWidget(self.due_date_input)
        layout.addWidget(self.add_task_button)
        layout.addWidget(QLabel("Update Status:"))
        layout.addWidget(self.status_selector)
        layout.addWidget(self.update_status_button)
        layout.addWidget(self.delete_task_button)
        self.tasks_tab.setLayout(layout)
        self.tabs.addTab(self.tasks_tab, "Tasks")

        # Connect Signals
        self.add_task_button.clicked.connect(self.assign_task)
        self.update_status_button.clicked.connect(self.update_task_status)
        self.delete_task_button.clicked.connect(self.delete_task)
        self.filter_button.clicked.connect(self.filter_tasks)

    def update_client_filter(self):
        """Updates the client filter combobox."""
        current_filter = self.client_filter.currentText() # Preserve selection
        self.client_filter.clear()
        self.client_filter.addItem("All Clients")
        self.client_filter.addItems(client_data.keys())
        # Restore selection if possible
        index = self.client_filter.findText(current_filter)
        if index >=0:
            self.client_filter.setCurrentIndex(index)

        # Update also the task client selector
        current_client = self.client_selector.currentText()
        self.client_selector.clear()
        self.client_selector.addItems(client_data.keys())
        client_index = self.client_selector.findText(current_client)
        if client_index >=0:
             self.client_selector.setCurrentIndex(client_index)

        # Update the notification client selector too
        current_notify_client = self.client_selector_notify.currentText()
        self.client_selector_notify.clear()
        self.client_selector_notify.addItem("ALL")
        self.client_selector_notify.addItems(client_data.keys())
        notify_index = self.client_selector_notify.findText(current_notify_client)
        if notify_index >= 0:
            self.client_selector_notify.setCurrentIndex(notify_index)



    def filter_tasks(self):
        selected_client = self.client_filter.currentText()
        date_order = self.date_order_filter.currentText()
        self.refresh_task_table(selected_client, date_order)

    def refresh_task_table(self, client_filter="All Clients", date_order="Ascending"):
      try:
        self.task_table.setRowCount(0)
        filtered_tasks = []

        # Filter by client
        for client_id, task_list in tasks.items():
            if client_filter == "All Clients" or client_id == client_filter:
                for task in task_list:
                    filtered_tasks.append((client_id, task))

        # Sort by due date
        filtered_tasks.sort(key=lambda x: x[1]["due_date"], reverse=(date_order == "Descending"))

        # Populate the table
        for client_id, task in filtered_tasks:
            row_position = self.task_table.rowCount()
            self.task_table.insertRow(row_position)
            self.task_table.setItem(row_position, 0, QTableWidgetItem(client_id))
            self.task_table.setItem(row_position, 1, QTableWidgetItem(task["description"]))
            self.task_table.setItem(row_position, 2, QTableWidgetItem(task["due_date"]))
            self.task_table.setItem(row_position, 3, QTableWidgetItem(task["status"]))
      except Exception as e:
            QMessageBox.critical(self,"Error", f"Failed to refresh task table: {e}")


    def update_task_in_json(self, row, column):
        try:
            client_id_item = self.task_table.item(row, 0)
            description_item = self.task_table.item(row, 1)
            due_date_item = self.task_table.item(row, 2)
            status_item = self.task_table.item(row, 3)

            if client_id_item is None or description_item is None or due_date_item is None or status_item is None:
                return

            client_id = client_id_item.text()
            if client_id in tasks:
                # Find the index of the task within the client's task list
                task_index = -1
                for i, task in enumerate(tasks[client_id]):
                    if (task["description"] == description_item.text() and
                        task["due_date"] == due_date_item.text() and
                        task["status"] == status_item.text()):
                        task_index = i
                        break

                if task_index != -1:
                    updated_value = self.task_table.item(row, column).text()
                    if column == 1:
                        tasks[client_id][task_index]["description"] = updated_value
                    elif column == 2:
                        tasks[client_id][task_index]["due_date"] = updated_value
                    elif column == 3:
                        tasks[client_id][task_index]["status"] = updated_value

                    save_data()
                    # Send update to client
                    send_update_to_client(client_id, "task_update_admin", {
                        "task_id": task_index,
                        "description": tasks[client_id][task_index]["description"],
                        "due_date": tasks[client_id][task_index]["due_date"],
                        "status": tasks[client_id][task_index]["status"]
                    })
        except Exception as e:
            QMessageBox.critical(self,"Error", f"Failed to update task in JSON: {e}")


    def assign_task(self):
        client_id = self.client_selector.currentText()
        task_description = self.task_input.toPlainText().strip()
        due_date = self.due_date_input.text().strip()
        if client_id and task_description and due_date:
            if client_id in client_data:
                if client_id not in tasks:
                    tasks[client_id] = []
                new_task = {"description": task_description, "due_date": due_date, "status": "Pending"}
                tasks[client_id].append(new_task)
                save_data()
                self.refresh_task_table()

                # Send the new task to the client.  Include task_id.
                task_id = len(tasks[client_id]) -1
                send_update_to_client(client_id, "new_task", {"task_id": task_id, **new_task}) # Send task with ID

            else:
                QMessageBox.warning(self, "Error", "Client ID does not exist!")
        else:
             QMessageBox.warning(self, "Error", "Please enter task details.")

        self.task_input.clear()
        #Don't clear the client selector
        self.due_date_input.clear()

    def update_task_status(self):
        selected_row = self.task_table.currentRow()
        if selected_row >= 0:
            client_id = self.task_table.item(selected_row, 0).text()
            if client_id in tasks:
                # Find the index of the task within the client's task list
                task_index = -1
                for i, task in enumerate(tasks[client_id]):
                    if (task["description"] == self.task_table.item(selected_row,1).text() and
                        task["due_date"] == self.task_table.item(selected_row,2).text() and
                        task["status"] == self.task_table.item(selected_row,3).text()
                        ):
                        task_index = i
                        break
                if task_index != -1:
                    new_status = self.status_selector.currentText()
                    tasks[client_id][task_index]["status"] = new_status
                    save_data()
                    self.refresh_task_table()
                    # Send update to client
                    send_update_to_client(client_id, "task_update_admin", {"task_id":task_index, "description":tasks[client_id][task_index]["description"],"due_date":tasks[client_id][task_index]["due_date"], "status": tasks[client_id][task_index]["status"]})
        else:
            QMessageBox.warning(self, "Error", "Please select a task to update!")

    def delete_task(self):
        selected_row = self.task_table.currentRow()
        if selected_row >= 0:
            client_id = self.task_table.item(selected_row, 0).text()
            if client_id in tasks:
                # Find the index of the task
                task_index = -1
                for i, task in enumerate(tasks[client_id]):
                    if (task["description"] == self.task_table.item(selected_row,1).text() and
                        task["due_date"] == self.task_table.item(selected_row,2).text() and
                        task["status"] == self.task_table.item(selected_row,3).text()
                        ):
                            task_index = i
                            break
                if task_index!=-1:
                    confirm = QMessageBox.question(self, "Confirm Deletion", "Are you sure you want to delete this task?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if confirm == QMessageBox.StandardButton.Yes:
                        deleted_task = tasks[client_id].pop(task_index)  # Remove the task
                        save_data()
                        self.refresh_task_table()
                        # Send task deletion notification to client
                        send_update_to_client(client_id, "delete_task", {"task_id": task_index})  # Send task_id
        else:
            QMessageBox.warning(self, "Error", "Please select a task to delete!")

    def setup_notifications_tab(self):
        self.notifications_tab = QWidget()
        layout = QVBoxLayout()

        # Notification list
        self.notification_list = QTableWidget()
        self.notification_list.setColumnCount(4)
        self.notification_list.setHorizontalHeaderLabels(["ID", "Client ID", "Message", "Status"])
        self.notification_list.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers) # Make read-only
        layout.addWidget(QLabel("Existing Notifications:"))
        layout.addWidget(self.notification_list)


        self.notification_input = QTextEdit()
        self.client_selector_notify = QComboBox() # Created *before* update_client_filter
        self.send_notification_button = QPushButton("Send Notification")
        self.delete_notification_button = QPushButton("Delete Notification")

        layout.addWidget(QLabel("Send Notification to Client (Select 'ALL' for all clients):"))
        layout.addWidget(self.client_selector_notify)
        layout.addWidget(QLabel("Message:"))
        layout.addWidget(self.notification_input)
        layout.addWidget(self.send_notification_button)
        layout.addWidget(self.delete_notification_button)
        self.notifications_tab.setLayout(layout)
        self.tabs.addTab(self.notifications_tab, "Notifications")
        self.send_notification_button.clicked.connect(self.send_notification)
        self.delete_notification_button.clicked.connect(self.delete_selected_notification)


    def send_notification(self):
        global next_notification_id
        client_id = self.client_selector_notify.currentText()
        message = self.notification_input.toPlainText().strip()

        if message:
            timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
            notification = {
                "id": next_notification_id,
                "client_id": client_id,
                "message": message,
                "status": "unread",
                "timestamp": timestamp,
                "read_timestamp": None  # Will be set when read
            }

            notifications.append(notification)
            next_notification_id += 1
            save_data()
            QMessageBox.information(self, "Success", "Notification sent!")
            self.refresh_notification_list()  # Refresh the UI

            # **Send notification to the appropriate client(s)**
            if client_id == "ALL":
                for cid in clients:  # Send to all connected clients
                    send_update_to_client(cid, "new_notification", notification)
            elif client_id in clients:
                send_update_to_client(client_id, "new_notification", notification)

            self.notification_input.clear()  # Clear input field
        else:
            QMessageBox.warning(self, "Error", "Please enter a notification message")

    def refresh_notification_list(self):
        """Refreshes the notification list in the UI."""
        self.notification_list.setRowCount(0)  # Clear existing rows
        for notification in notifications:
            row_pos = self.notification_list.rowCount()
            self.notification_list.insertRow(row_pos)
            self.notification_list.setItem(row_pos, 0, QTableWidgetItem(str(notification["id"])))
            self.notification_list.setItem(row_pos, 1, QTableWidgetItem(notification["client_id"]))
            self.notification_list.setItem(row_pos, 2, QTableWidgetItem(notification["message"]))
            self.notification_list.setItem(row_pos, 3, QTableWidgetItem(notification["status"]))


    def delete_selected_notification(self):
        selected_row = self.notification_list.currentRow()
        if selected_row >= 0:
            notification_id = int(self.notification_list.item(selected_row, 0).text())
            # Find the notification to get client_id before deletion
            notification_to_delete = next((n for n in notifications if n["id"] == notification_id), None)
            if notification_to_delete:
                client_id = notification_to_delete["client_id"]
                notifications[:] = [n for n in notifications if n["id"] != notification_id]
                save_data()
                self.refresh_notification_list()

                # Send delete command to relevant clients
                if client_id == "ALL":
                    for cid in clients:
                        send_update_to_client(cid, "delete_notification", {"id": notification_id})
                elif client_id in clients:
                    send_update_to_client(client_id, "delete_notification", {"id": notification_id})

    def load_existing_data(self):
        load_data()
        self.refresh_client_table()
        self.refresh_task_table()
        self.refresh_notification_list()
        self.update_client_filter() # Added - Must be called *AFTER* combo boxes are created

    def refresh_all_tabs(self):
        self.refresh_client_table()
        self.refresh_task_table()
        self.refresh_notification_list()
        self.update_client_filter()

    def handle_client_update(self, update_type, data):
        if update_type == "task_update":
            self.refresh_task_table()
        elif update_type == "notification_update":
            self.refresh_notification_list()
        elif update_type == "client_update":
            self.refresh_client_table()
            self.update_client_filter()


# --- Main Application Startup ---

if __name__ == "__main__":
    app = QApplication(sys.argv)
     # Load server config, show dialog if it's the first run
    host, port = load_server_config()
    if host == DEFAULT_HOST and port == DEFAULT_PORT:  # Likely first run
        config_dialog = ServerConfigDialog()
        if config_dialog.exec() == QDialog.DialogCode.Accepted:
            host, port = config_dialog.get_config()
            save_server_config(host, port)
        else:
            sys.exit(0)  # Exit if the user cancels the config

    # Start server and Admin Panel
    load_data()  # Load existing data
    threading.Thread(target=start_server, args=(host, port), daemon=True).start()
    window = AdminPanel(host,port)
    window.show()
    sys.exit(app.exec())
