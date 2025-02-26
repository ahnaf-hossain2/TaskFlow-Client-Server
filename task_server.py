import socket
import threading
import json
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
import os
from ttkthemes import ThemedTk
from datetime import datetime
import time
from tkcalendar import DateEntry
from tkinter import scrolledtext

class TaskDatabase:
    def __init__(self, db_file="task_server.db"):
        self.db_file = db_file
        self.create_tables()

    def create_tables(self):
        """Create the necessary database tables if they don't exist."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        # Create clients table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            client_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            ip_address TEXT,
            last_seen TEXT,
            status TEXT DEFAULT 'Active'
        )
        ''')

        # Create tasks table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            due_date TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (client_id) REFERENCES clients (client_id)
        )
        ''')

        # Create notifications table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            message TEXT NOT NULL,
            created_at TEXT,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY (client_id) REFERENCES clients (client_id)
        )
        ''')

        # Create reminders table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            reminder_time TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY (task_id) REFERENCES tasks (task_id)
        )
        ''')

        conn.commit()
        conn.close()

    def add_client(self, client_id, name, ip_address=""):
        """Add a new client to the database."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO clients (client_id, name, ip_address, last_seen) VALUES (?, ?, ?, ?)",
                (client_id, name, ip_address, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
            return True, "Client added successfully"
        except sqlite3.IntegrityError:
            return False, "Client ID already exists"
        except Exception as e:
            return False, f"Error adding client: {str(e)}"
        finally:
            conn.close()

    def update_client(self, client_id, name=None, ip_address=None, status=None):
        """Update client information."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        update_fields = []
        params = []

        if name is not None:
            update_fields.append("name = ?")
            params.append(name)

        if ip_address is not None:
            update_fields.append("ip_address = ?")
            params.append(ip_address)

        if status is not None:
            update_fields.append("status = ?")
            params.append(status)

        if not update_fields:
            conn.close()
            return False, "No fields to update"

        update_fields.append("last_seen = ?")
        params.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        params.append(client_id)

        try:
            cursor.execute(
                f"UPDATE clients SET {', '.join(update_fields)} WHERE client_id = ?",
                params
            )
            conn.commit()
            return True, "Client updated successfully"
        except Exception as e:
            return False, f"Error updating client: {str(e)}"
        finally:
            conn.close()

    def delete_client(self, client_id):
        """Delete a client and all associated tasks and notifications."""
        conn = sqlite3.connect(self.db_file)
        conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints
        cursor = conn.cursor()

        try:
            cursor.execute("BEGIN TRANSACTION")

            # Delete associated reminders
            cursor.execute(
                "DELETE FROM reminders WHERE task_id IN (SELECT task_id FROM tasks WHERE client_id = ?)",
                (client_id,)
            )

            # Delete associated tasks
            cursor.execute("DELETE FROM tasks WHERE client_id = ?", (client_id,))

            # Delete associated notifications
            cursor.execute("DELETE FROM notifications WHERE client_id = ?", (client_id,))

            # Delete the client
            cursor.execute("DELETE FROM clients WHERE client_id = ?", (client_id,))

            cursor.execute("COMMIT")
            return True, "Client and related data deleted successfully"
        except Exception as e:
            cursor.execute("ROLLBACK")
            return False, f"Error deleting client: {str(e)}"
        finally:
            conn.close()

    def get_client(self, client_id):
        """Get client information by ID."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT client_id, name, ip_address, last_seen, status FROM clients WHERE client_id = ?",
                (client_id,)
            )
            client = cursor.fetchone()
            if client:
                return {
                    "client_id": client[0],
                    "name": client[1],
                    "ip_address": client[2],
                    "last_seen": client[3],
                    "status": client[4]
                }
            else:
                return None
        finally:
            conn.close()

    def get_all_clients(self, active_only=False):
        """Get all clients."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        try:
            if active_only:
                cursor.execute(
                    "SELECT client_id, name, ip_address, last_seen, status FROM clients WHERE status = 'Active'"
                )
            else:
                cursor.execute(
                    "SELECT client_id, name, ip_address, last_seen, status FROM clients"
                )

            clients = []
            for row in cursor.fetchall():
                clients.append({
                    "client_id": row[0],
                    "name": row[1],
                    "ip_address": row[2],
                    "last_seen": row[3],
                    "status": row[4]
                })

            return clients
        finally:
            conn.close()

    def add_task(self, client_id, title, description="", due_date=""):
        """Add a new task for a client."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            cursor.execute(
                """
                INSERT INTO tasks (client_id, title, description, due_date, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (client_id, title, description, due_date, now, now)
            )
            conn.commit()
            return True, cursor.lastrowid
        except Exception as e:
            return False, f"Error adding task: {str(e)}"
        finally:
            conn.close()

    def update_task(self, task_id, title=None, description=None, due_date=None, status=None):
        """Update task information."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        update_fields = []
        params = []

        if title is not None:
            update_fields.append("title = ?")
            params.append(title)

        if description is not None:
            update_fields.append("description = ?")
            params.append(description)

        if due_date is not None:
            update_fields.append("due_date = ?")
            params.append(due_date)

        if status is not None:
            update_fields.append("status = ?")
            params.append(status)

        if not update_fields:
            conn.close()
            return False, "No fields to update"

        update_fields.append("updated_at = ?")
        params.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        params.append(task_id)

        try:
            cursor.execute(
                f"UPDATE tasks SET {', '.join(update_fields)} WHERE task_id = ?",
                params
            )
            conn.commit()
            return True, "Task updated successfully"
        except Exception as e:
            return False, f"Error updating task: {str(e)}"
        finally:
            conn.close()

    def delete_task(self, task_id):
        """Delete a task and associated reminders."""
        conn = sqlite3.connect(self.db_file)
        conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints
        cursor = conn.cursor()

        try:
            cursor.execute("BEGIN TRANSACTION")

            # Delete associated reminders
            cursor.execute("DELETE FROM reminders WHERE task_id = ?", (task_id,))

            # Delete the task
            cursor.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))

            cursor.execute("COMMIT")
            return True, "Task deleted successfully"
        except Exception as e:
            cursor.execute("ROLLBACK")
            return False, f"Error deleting task: {str(e)}"
        finally:
            conn.close()

    def get_task(self, task_id):
        """Get task information by ID."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT t.task_id, t.client_id, c.name, t.title, t.description, t.due_date, t.status, t.created_at, t.updated_at
                FROM tasks t
                JOIN clients c ON t.client_id = c.client_id
                WHERE t.task_id = ?
                """,
                (task_id,)
            )
            task = cursor.fetchone()
            if task:
                return {
                    "task_id": task[0],
                    "client_id": task[1],
                    "client_name": task[2],
                    "title": task[3],
                    "description": task[4],
                    "due_date": task[5],
                    "status": task[6],
                    "created_at": task[7],
                    "updated_at": task[8]
                }
            else:
                return None
        finally:
            conn.close()

    def get_client_tasks(self, client_id):
        """Get all tasks for a specific client."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT task_id, title, description, due_date, status, created_at, updated_at
                FROM tasks
                WHERE client_id = ?
                ORDER BY
                    CASE status
                        WHEN 'Pending' THEN 1
                        WHEN 'In Progress' THEN 2
                        WHEN 'Completed' THEN 3
                        ELSE 4
                    END,
                    due_date ASC
                """,
                (client_id,)
            )

            tasks = []
            for row in cursor.fetchall():
                tasks.append({
                    "task_id": row[0],
                    "title": row[1],
                    "description": row[2],
                    "due_date": row[3],
                    "status": row[4],
                    "created_at": row[5],
                    "updated_at": row[6]
                })

            return tasks
        finally:
            conn.close()

    def get_all_tasks(self):
        """Get all tasks with client information."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT t.task_id, t.client_id, c.name, t.title, t.description, t.due_date, t.status
                FROM tasks t
                JOIN clients c ON t.client_id = c.client_id
                ORDER BY
                    CASE t.status
                        WHEN 'Pending' THEN 1
                        WHEN 'In Progress' THEN 2
                        WHEN 'Completed' THEN 3
                        ELSE 4
                    END,
                    t.due_date ASC
                """
            )

            tasks = []
            for row in cursor.fetchall():
                tasks.append({
                    "task_id": row[0],
                    "client_id": row[1],
                    "client_name": row[2],
                    "title": row[3],
                    "description": row[4],
                    "due_date": row[5],
                    "status": row[6]
                })

            return tasks
        finally:
            conn.close()

    def add_notification(self, message, client_id=None):
        """Add a notification for a specific client or all clients (broadcast)."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            if client_id is None:
                # Broadcast to all active clients
                clients = self.get_all_clients(active_only=True)

                for client in clients:
                    cursor.execute(
                        "INSERT INTO notifications (client_id, message, created_at) VALUES (?, ?, ?)",
                        (client["client_id"], message, now)
                    )
            else:
                # Send to specific client
                cursor.execute(
                    "INSERT INTO notifications (client_id, message, created_at) VALUES (?, ?, ?)",
                    (client_id, message, now)
                )

            conn.commit()
            return True, "Notification added successfully"
        except Exception as e:
            return False, f"Error adding notification: {str(e)}"
        finally:
            conn.close()

    def get_pending_notifications(self, client_id):
        """Get all pending notifications for a client."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT notification_id, message, created_at
                FROM notifications
                WHERE client_id = ? AND status = 'Pending'
                ORDER BY created_at ASC
                """,
                (client_id,)
            )

            notifications = []
            for row in cursor.fetchall():
                notifications.append({
                    "notification_id": row[0],
                    "message": row[1],
                    "created_at": row[2]
                })

            return notifications
        finally:
            conn.close()

    def mark_notification_sent(self, notification_id):
        """Mark a notification as sent."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        try:
            cursor.execute(
                "UPDATE notifications SET status = 'Sent' WHERE notification_id = ?",
                (notification_id,)
            )
            conn.commit()
            return True
        except Exception as e:
            return False
        finally:
            conn.close()

    def add_reminder(self, task_id, reminder_time):
        """Add a reminder for a task."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO reminders (task_id, reminder_time) VALUES (?, ?)",
                (task_id, reminder_time)
            )
            conn.commit()
            return True, cursor.lastrowid
        except Exception as e:
            return False, f"Error adding reminder: {str(e)}"
        finally:
            conn.close()

    def get_due_reminders(self):
        """Get all due reminders."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            cursor.execute(
                """
                SELECT r.reminder_id, r.task_id, t.title, t.client_id
                FROM reminders r
                JOIN tasks t ON r.task_id = t.task_id
                WHERE r.reminder_time <= ? AND r.status = 'Pending'
                """,
                (now,)
            )

            reminders = []
            for row in cursor.fetchall():
                reminders.append({
                    "reminder_id": row[0],
                    "task_id": row[1],
                    "task_title": row[2],
                    "client_id": row[3]
                })

            return reminders
        finally:
            conn.close()

    def mark_reminder_sent(self, reminder_id):
        """Mark a reminder as sent."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        try:
            cursor.execute(
                "UPDATE reminders SET status = 'Sent' WHERE reminder_id = ?",
                (reminder_id,)
            )
            conn.commit()
            return True
        except Exception as e:
            return False
        finally:
            conn.close()

class TaskServer:
    def __init__(self, host='0.0.0.0', port=5555):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False

        # Database
        self.db = TaskDatabase()

        # Connected clients {client_id: {'socket': sock, 'address': addr}}
        self.clients = {}

        # Callbacks - will be set by GUI
        self.on_client_connected = None
        self.on_client_disconnected = None
        self.on_task_updated = None

        # Thread for checking reminders
        self.reminder_thread = None
        self.reminder_stop_event = threading.Event()

    def start(self):
        """Start the server."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)

            self.running = True

            # Start accepting client connections in a separate thread
            accept_thread = threading.Thread(target=self.accept_connections)
            accept_thread.daemon = True
            accept_thread.start()

            # Start reminder thread
            self.reminder_stop_event.clear()
            self.reminder_thread = threading.Thread(target=self.check_reminders)
            self.reminder_thread.daemon = True
            self.reminder_thread.start()

            return True, f"Server started on {self.host}:{self.port}"
        except Exception as e:
            self.running = False
            return False, f"Failed to start server: {str(e)}"

    def stop(self):
        """Stop the server."""
        if not self.running:
            return

        self.running = False

        # Notify all clients that server is shutting down
        for client_id, client_info in list(self.clients.items()):
            try:
                self.send_message(client_id, {
                    "type": "server_shutdown",
                    "message": "Server is shutting down"
                })
                client_info["socket"].close()
            except:
                pass

        # Stop reminder thread
        self.reminder_stop_event.set()

        # Close server socket
        if self.server_socket:
            self.server_socket.close()

        self.clients.clear()

    def accept_connections(self):
        """Accept incoming client connections."""
        self.server_socket.settimeout(1)  # Use non-blocking with timeout

        while self.running:
            try:
                client_socket, client_address = self.server_socket.accept()

                # Start a new thread to handle the client
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, client_address)
                )
                client_thread.daemon = True
                client_thread.start()

            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"Error accepting connection: {str(e)}")

    def handle_client(self, client_socket, client_address):
        """Handle a client connection."""
        client_id = None

        try:
            # Wait for login message
            message = self.receive_message(client_socket)

            if not message or message.get("type") != "login":
                client_socket.close()
                return

            client_id = message.get("client_id")

            if not client_id:
                client_socket.close()
                return

            # Check if client exists in database
            client = self.db.get_client(client_id)

            if not client:
                # Create new client
                client_name = f"Client-{client_id}"
                success, _ = self.db.add_client(client_id, client_name, client_address[0])
                if not success:
                    client_socket.close()
                    return

                client = self.db.get_client(client_id)
            elif client["status"] != "Active":
                # Client is deactivated
                self.send_message_direct(client_socket, {
                    "type": "login_response",
                    "status": "error",
                    "message": "Your account has been deactivated"
                })
                client_socket.close()
                return
            else:
                # Update client IP address
                self.db.update_client(client_id, ip_address=client_address[0])

            # Send login response
            self.send_message_direct(client_socket, {
                "type": "login_response",
                "status": "success",
                "name": client["name"]
            })

            # Add client to connected clients
            self.clients[client_id] = {
                "socket": client_socket,
                "address": client_address
            }

            # Notify GUI
            if self.on_client_connected:
                self.on_client_connected(client_id)

            # Send pending notifications
            self.send_pending_notifications(client_id)

            # Send task list
            tasks = self.db.get_client_tasks(client_id)
            self.send_message(client_id, {
                "type": "task_list",
                "tasks": tasks
            })

            # Handle messages from client
            while self.running:
                message = self.receive_message(client_socket)

                if not message:
                    break

                self.handle_client_message(client_id, message)

        except Exception as e:
            print(f"Error handling client {client_id}: {str(e)}")

        finally:
            # Clean up
            if client_id in self.clients:
                del self.clients[client_id]

            try:
                client_socket.close()
            except:
                pass

            # Notify GUI
            if client_id and self.on_client_disconnected:
                self.on_client_disconnected(client_id)

    def handle_client_message(self, client_id, message):
        """Handle a message from a client."""
        msg_type = message.get("type")

        if msg_type == "task_update":
            # Update task status
            task_id = message.get("task_id")
            status = message.get("status")

            success, _ = self.db.update_task(task_id, status=status)

            if success and self.on_task_updated:
                self.on_task_updated()

    def send_message(self, client_id, message):
        """Send a message to a specific client."""
        if client_id not in self.clients:
            return False

        try:
            return self.send_message_direct(self.clients[client_id]["socket"], message)
        except:
            # Handle disconnection
            if client_id in self.clients:
                del self.clients[client_id]

            if self.on_client_disconnected:
                self.on_client_disconnected(client_id)

            return False

    def send_message_direct(self, sock, message):
        """Send a message directly to a socket."""
        try:
            message_json = json.dumps(message)
            message_bytes = message_json.encode('utf-8')
            length = len(message_bytes)
            length_bytes = length.to_bytes(4, byteorder='big')
            sock.sendall(length_bytes + message_bytes)
            return True
        except:
            raise

    def receive_message(self, sock):
        """Receive a message from a socket."""
        try:
            # Set a timeout to prevent blocking forever
            sock.settimeout(30)

            # Receive message length (4 bytes)
            length_bytes = sock.recv(4)
            if not length_bytes:
                return None

            length = int.from_bytes(length_bytes, byteorder='big')

            # Receive data
            data = b''
            while len(data) < length:
                packet = sock.recv(min(length - len(data), 4096))
                if not packet:
                    return None
                data += packet

            # Reset timeout
            sock.settimeout(None)

            # Decode and parse
            message_json = data.decode('utf-8')
            message = json.loads(message_json)

            return message
        except:
            return None

    def broadcast_message(self, message):
        """Broadcast a message to all connected clients."""
        for client_id in list(self.clients.keys()):
            self.send_message(client_id, message)

    def assign_task(self, client_id, title, description="", due_date=""):
        """Assign a new task to a client."""
        success, task_id = self.db.add_task(client_id, title, description, due_date)

        if not success:
            return False, f"Failed to add task: {task_id}"

        # Get the complete task information
        task = self.db.get_task(task_id)

        # Notify client if connected
        if client_id in self.clients:
            self.send_message(client_id, {
                "type": "new_task",
                "task_id": task_id,
                "title": title,
                "description": description,
                "due_date": due_date,
                "status": "Pending"
            })

        return True, task_id

    def update_task(self, task_id, title=None, description=None, due_date=None, status=None):
        """Update a task and notify the client."""
        # Get original task to get client_id
        original_task = self.db.get_task(task_id)
        if not original_task:
            return False, "Task not found"

        # Update task in database
        success, message = self.db.update_task(task_id, title, description, due_date, status)

        if not success:
            return False, message

        # Get updated task
        updated_task = self.db.get_task(task_id)
        client_id = updated_task["client_id"]

        # Notify client if connected
        if client_id in self.clients:
            self.send_message(client_id, {
                "type": "task_updated",
                "task_id": task_id,
                "title": updated_task["title"],
                "description": updated_task["description"],
                "due_date": updated_task["due_date"],
                "status": updated_task["status"]
            })

        # Notify GUI
        if self.on_task_updated:
            self.on_task_updated()

        return True, "Task updated successfully"

    def delete_task(self, task_id):
        """Delete a task and notify the client."""
        # Get original task to get client_id
        task = self.db.get_task(task_id)
        if not task:
            return False, "Task not found"

        client_id = task["client_id"]

        # Delete task from database
        success, message = self.db.delete_task(task_id)

        if not success:
            return False, message

        # Notify client if connected
        if client_id in self.clients:
            self.send_message(client_id, {
                "type": "task_removed",
                "task_id": task_id
            })

        # Notify GUI
        if self.on_task_updated:
            self.on_task_updated()

        return True, "Task deleted successfully"

    def send_notification(self, message, client_id=None):
        """Send a notification to a specific client or broadcast to all."""
        # Add to database
        success, result = self.db.add_notification(message, client_id)

        if not success:
            return False, result

        # Send to client(s)
        if client_id is None:
            # Broadcast to all connected clients
            for cid in list(self.clients.keys()):
                self.send_message(cid, {
                    "type": "notification",
                    "message": message
                })
        else:
            # Send to specific client if connected
            if client_id in self.clients:
                self.send_message(client_id, {
                    "type": "notification",
                    "message": message
                })

        return True, "Notification sent successfully"

    def send_pending_notifications(self, client_id):
        """Send all pending notifications to a client."""
        notifications = self.db.get_pending_notifications(client_id)

        for notification in notifications:
            if self.send_message(client_id, {
                "type": "notification",
                "message": notification["message"]
            }):
                self.db.mark_notification_sent(notification["notification_id"])

def check_reminders(self):
        """Periodically check for due reminders."""
        while not self.reminder_stop_event.is_set():
            try:
                # Get all due reminders
                due_reminders = self.db.get_due_reminders()

                # Process each reminder
                for reminder in due_reminders:
                    client_id = reminder["client_id"]
                    task = self.db.get_task(reminder["task_id"])

                    if task:
                        # Create reminder message
                        message = f"REMINDER: Task '{task['title']}' is due soon!"

                        # Send notification
                        self.db.add_notification(message, client_id)

                        # If client is connected, send directly
                        if client_id in self.clients:
                            self.send_message(client_id, {
                                "type": "notification",
                                "message": message
                            })

                        # Mark reminder as sent
                        self.db.mark_reminder_sent(reminder["reminder_id"])

            except Exception as e:
                print(f"Error checking reminders: {str(e)}")

            # Sleep for 60 seconds
            for _ in range(60):
                if self.reminder_stop_event.is_set():
                    break
                time.sleep(1)


class TaskServerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Task Management Server")
        self.root.geometry("1200x750")

        # Initialize the server
        self.server = TaskServer()

        # Set server callbacks
        self.server.on_client_connected = self.on_client_connected
        self.server.on_client_disconnected = self.on_client_disconnected
        self.server.on_task_updated = self.on_task_updated

        # Initialize the UI
        self.setup_ui()

        # Start periodic refresh
        self.periodic_refresh()

    def setup_ui(self):
        """Set up the user interface."""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Dashboard tab
        self.dashboard_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.dashboard_frame, text="Dashboard")
        self.setup_dashboard()

        # Clients tab
        self.clients_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.clients_frame, text="Clients")
        self.setup_clients_tab()

        # Tasks tab
        self.tasks_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.tasks_frame, text="Tasks")
        self.setup_tasks_tab()

        # Notifications tab
        self.notifications_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.notifications_frame, text="Notifications")
        self.setup_notifications_tab()

        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Server stopped")

        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)

        self.server_button = ttk.Button(self.status_frame, text="Start Server", command=self.toggle_server)
        self.server_button.pack(side=tk.LEFT, padx=5)

        ttk.Label(self.status_frame, textvariable=self.status_var).pack(side=tk.LEFT, padx=10)

    def setup_dashboard(self):
        """Set up the dashboard tab."""
        # Create left and right frames for split view
        left_frame = ttk.LabelFrame(self.dashboard_frame, text="Active Clients")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        right_frame = ttk.LabelFrame(self.dashboard_frame, text="Pending Tasks")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Active clients table
        columns = ("client_id", "name", "status")
        self.dashboard_clients_table = ttk.Treeview(left_frame, columns=columns, show="headings")

        # Set column headings
        self.dashboard_clients_table.heading("client_id", text="Client ID")
        self.dashboard_clients_table.heading("name", text="Name")
        self.dashboard_clients_table.heading("status", text="Status")

        # Set column widths
        self.dashboard_clients_table.column("client_id", width=80)
        self.dashboard_clients_table.column("name", width=150)
        self.dashboard_clients_table.column("status", width=100)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.dashboard_clients_table.yview)
        self.dashboard_clients_table.configure(yscroll=scrollbar.set)

        # Pack
        self.dashboard_clients_table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Pending tasks table
        columns = ("task_id", "client_name", "title", "due_date", "status")
        self.dashboard_tasks_table = ttk.Treeview(right_frame, columns=columns, show="headings")

        # Set column headings
        self.dashboard_tasks_table.heading("task_id", text="Task ID")
        self.dashboard_tasks_table.heading("client_name", text="Client")
        self.dashboard_tasks_table.heading("title", text="Title")
        self.dashboard_tasks_table.heading("due_date", text="Due Date")
        self.dashboard_tasks_table.heading("status", text="Status")

        # Set column widths
        self.dashboard_tasks_table.column("task_id", width=60)
        self.dashboard_tasks_table.column("client_name", width=100)
        self.dashboard_tasks_table.column("title", width=150)
        self.dashboard_tasks_table.column("due_date", width=100)
        self.dashboard_tasks_table.column("status", width=80)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.dashboard_tasks_table.yview)
        self.dashboard_tasks_table.configure(yscroll=scrollbar.set)

        # Pack
        self.dashboard_tasks_table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Add color tag for pending tasks
        self.dashboard_tasks_table.tag_configure('pending', background='#ffcccc')

    def setup_clients_tab(self):
        """Set up the clients tab."""
        # Create left frame for client list and right frame for client details
        left_frame = ttk.Frame(self.clients_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        right_frame = ttk.LabelFrame(self.clients_frame, text="Client Details")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Clients table
        columns = ("client_id", "name", "ip_address", "last_seen", "status", "connected")
        self.clients_table = ttk.Treeview(left_frame, columns=columns, show="headings")

        # Set column headings
        self.clients_table.heading("client_id", text="Client ID")
        self.clients_table.heading("name", text="Name")
        self.clients_table.heading("ip_address", text="IP Address")
        self.clients_table.heading("last_seen", text="Last Seen")
        self.clients_table.heading("status", text="Status")
        self.clients_table.heading("connected", text="Connected")

        # Set column widths
        self.clients_table.column("client_id", width=80)
        self.clients_table.column("name", width=150)
        self.clients_table.column("ip_address", width=120)
        self.clients_table.column("last_seen", width=150)
        self.clients_table.column("status", width=80)
        self.clients_table.column("connected", width=80)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.clients_table.yview)
        self.clients_table.configure(yscroll=scrollbar.set)

        # Pack
        self.clients_table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind selection event
        self.clients_table.bind("<<TreeviewSelect>>", self.on_client_selected)

        # Action buttons
        button_frame = ttk.Frame(left_frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)

        ttk.Button(button_frame, text="Add Client", command=self.add_client).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Edit", command=self.edit_client).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Toggle Status", command=self.toggle_client_status).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Delete", command=self.delete_client).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Refresh", command=self.refresh_clients).pack(side=tk.LEFT, padx=2)

        # Client details form
        self.client_details_frame = ttk.Frame(right_frame)
        self.client_details_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Client ID
        ttk.Label(self.client_details_frame, text="Client ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.client_id_var = tk.StringVar()
        ttk.Entry(self.client_details_frame, textvariable=self.client_id_var, state="readonly").grid(row=0, column=1, sticky=tk.W+tk.E, pady=5, padx=5)

        # Client Name
        ttk.Label(self.client_details_frame, text="Name:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.client_name_var = tk.StringVar()
        ttk.Entry(self.client_details_frame, textvariable=self.client_name_var).grid(row=1, column=1, sticky=tk.W+tk.E, pady=5, padx=5)

        # Status
        ttk.Label(self.client_details_frame, text="Status:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.client_status_var = tk.StringVar()
        status_combobox = ttk.Combobox(self.client_details_frame, textvariable=self.client_status_var, values=["Active", "Inactive"])
        status_combobox.grid(row=2, column=1, sticky=tk.W+tk.E, pady=5, padx=5)

        # Client's tasks
        ttk.Label(self.client_details_frame, text="Client Tasks:").grid(row=3, column=0, sticky=tk.W, pady=5)

        self.client_tasks_frame = ttk.Frame(self.client_details_frame)
        self.client_tasks_frame.grid(row=4, column=0, columnspan=2, sticky=tk.W+tk.E+tk.N+tk.S)

        columns = ("task_id", "title", "due_date", "status")
        self.client_tasks_table = ttk.Treeview(self.client_tasks_frame, columns=columns, show="headings", height=8)

        # Set column headings
        self.client_tasks_table.heading("task_id", text="Task ID")
        self.client_tasks_table.heading("title", text="Title")
        self.client_tasks_table.heading("due_date", text="Due Date")
        self.client_tasks_table.heading("status", text="Status")

        # Set column widths
        self.client_tasks_table.column("task_id", width=60)
        self.client_tasks_table.column("title", width=200)
        self.client_tasks_table.column("due_date", width=120)
        self.client_tasks_table.column("status", width=100)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(self.client_tasks_frame, orient=tk.VERTICAL, command=self.client_tasks_table.yview)
        self.client_tasks_table.configure(yscroll=scrollbar.set)

        # Pack
        self.client_tasks_table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Button frame
        button_frame = ttk.Frame(self.client_details_frame)
        button_frame.grid(row=5, column=0, columnspan=2, sticky=tk.W+tk.E, pady=10)

        ttk.Button(button_frame, text="Save Changes", command=self.save_client_changes).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Assign Task", command=self.assign_task_to_client).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Send Notification", command=self.send_notification_to_client).pack(side=tk.LEFT, padx=5)

    def setup_tasks_tab(self):
        """Set up the tasks tab."""
        # Create left frame for task list and right frame for task details
        left_frame = ttk.Frame(self.tasks_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        right_frame = ttk.LabelFrame(self.tasks_frame, text="Task Details")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tasks table
        columns = ("task_id", "client_id", "client_name", "title", "due_date", "status")
        self.tasks_table = ttk.Treeview(left_frame, columns=columns, show="headings")

        # Set column headings
        self.tasks_table.heading("task_id", text="Task ID")
        self.tasks_table.heading("client_id", text="Client ID")
        self.tasks_table.heading("client_name", text="Client Name")
        self.tasks_table.heading("title", text="Title")
        self.tasks_table.heading("due_date", text="Due Date")
        self.tasks_table.heading("status", text="Status")

        # Set column widths
        self.tasks_table.column("task_id", width=60)
        self.tasks_table.column("client_id", width=60)
        self.tasks_table.column("client_name", width=120)
        self.tasks_table.column("title", width=200)
        self.tasks_table.column("due_date", width=120)
        self.tasks_table.column("status", width=100)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.tasks_table.yview)
        self.tasks_table.configure(yscroll=scrollbar.set)

        # Pack
        self.tasks_table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Add color tag for pending tasks
        self.tasks_table.tag_configure('pending', background='#ffcccc')

        # Bind selection event
        self.tasks_table.bind("<<TreeviewSelect>>", self.on_task_selected)

        # Action buttons
        button_frame = ttk.Frame(left_frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)

        ttk.Button(button_frame, text="Add Task", command=self.add_task).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Edit", command=self.edit_task).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Delete", command=self.delete_task).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Refresh", command=self.refresh_tasks).pack(side=tk.LEFT, padx=2)

        # Task details form
        self.task_details_frame = ttk.Frame(right_frame)
        self.task_details_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Task ID
        ttk.Label(self.task_details_frame, text="Task ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.task_id_var = tk.StringVar()
        ttk.Entry(self.task_details_frame, textvariable=self.task_id_var, state="readonly").grid(row=0, column=1, sticky=tk.W+tk.E, pady=5, padx=5)

        # Client
        ttk.Label(self.task_details_frame, text="Client:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.task_client_var = tk.StringVar()
        self.task_client_combo = ttk.Combobox(self.task_details_frame, textvariable=self.task_client_var)
        self.task_client_combo.grid(row=1, column=1, sticky=tk.W+tk.E, pady=5, padx=5)

        # Title
        ttk.Label(self.task_details_frame, text="Title:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.task_title_var = tk.StringVar()
        ttk.Entry(self.task_details_frame, textvariable=self.task_title_var).grid(row=2, column=1, sticky=tk.W+tk.E, pady=5, padx=5)

        # Description
        ttk.Label(self.task_details_frame, text="Description:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.task_description_text = scrolledtext.ScrolledText(self.task_details_frame, width=40, height=5, wrap=tk.WORD)
        self.task_description_text.grid(row=3, column=1, sticky=tk.W+tk.E+tk.N+tk.S, pady=5, padx=5)

        # Due Date
        ttk.Label(self.task_details_frame, text="Due Date:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.task_due_date_frame = ttk.Frame(self.task_details_frame)
        self.task_due_date_frame.grid(row=4, column=1, sticky=tk.W, pady=5, padx=5)

        self.task_due_date_entry = DateEntry(self.task_due_date_frame, width=12, background='darkblue', foreground='white', borderwidth=2)
        self.task_due_date_entry.pack(side=tk.LEFT)

        # Time
        ttk.Label(self.task_due_date_frame, text="Time:").pack(side=tk.LEFT, padx=(10, 2))

        self.task_due_hour_var = tk.StringVar()
        hour_spin = ttk.Spinbox(self.task_due_date_frame, from_=0, to=23, width=3, textvariable=self.task_due_hour_var)
        hour_spin.pack(side=tk.LEFT)

        ttk.Label(self.task_due_date_frame, text=":").pack(side=tk.LEFT)

        self.task_due_minute_var = tk.StringVar()
        minute_spin = ttk.Spinbox(self.task_due_date_frame, from_=0, to=59, width=3, textvariable=self.task_due_minute_var)
        minute_spin.pack(side=tk.LEFT)

        # Status
        ttk.Label(self.task_details_frame, text="Status:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.task_status_var = tk.StringVar()
        status_combobox = ttk.Combobox(self.task_details_frame, textvariable=self.task_status_var, values=["Pending", "In Progress", "Completed"])
        status_combobox.grid(row=5, column=1, sticky=tk.W+tk.E, pady=5, padx=5)

        # Reminder
        ttk.Label(self.task_details_frame, text="Set Reminder:").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.reminder_frame = ttk.Frame(self.task_details_frame)
        self.reminder_frame.grid(row=6, column=1, sticky=tk.W, pady=5, padx=5)

        self.reminder_date_entry = DateEntry(self.reminder_frame, width=12, background='darkblue', foreground='white', borderwidth=2)
        self.reminder_date_entry.pack(side=tk.LEFT)

        ttk.Label(self.reminder_frame, text="Time:").pack(side=tk.LEFT, padx=(10, 2))

        self.reminder_hour_var = tk.StringVar()
        hour_spin = ttk.Spinbox(self.reminder_frame, from_=0, to=23, width=3, textvariable=self.reminder_hour_var)
        hour_spin.pack(side=tk.LEFT)

        ttk.Label(self.reminder_frame, text=":").pack(side=tk.LEFT)

        self.reminder_minute_var = tk.StringVar()
        minute_spin = ttk.Spinbox(self.reminder_frame, from_=0, to=59, width=3, textvariable=self.reminder_minute_var)
        minute_spin.pack(side=tk.LEFT)

        ttk.Button(self.reminder_frame, text="Add Reminder", command=self.add_reminder).pack(side=tk.LEFT, padx=10)

        # Button frame
        button_frame = ttk.Frame(self.task_details_frame)
        button_frame.grid(row=7, column=0, columnspan=2, sticky=tk.W+tk.E, pady=10)

        ttk.Button(button_frame, text="Save Changes", command=self.save_task_changes).pack(side=tk.LEFT, padx=5)

    def setup_notifications_tab(self):
        """Set up the notifications tab."""
        # Create main frame
        notification_frame = ttk.Frame(self.notifications_frame)
        notification_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Target selection
        target_frame = ttk.LabelFrame(notification_frame, text="Notification Target")
        target_frame.pack(fill=tk.X, padx=10, pady=10)

        self.notification_target_var = tk.StringVar(value="broadcast")
        broadcast_radio = ttk.Radiobutton(target_frame, text="Broadcast to All Clients", variable=self.notification_target_var, value="broadcast")
        broadcast_radio.pack(anchor=tk.W, padx=10, pady=5)

        specific_radio = ttk.Radiobutton(target_frame, text="Send to Specific Client", variable=self.notification_target_var, value="specific")
        specific_radio.pack(anchor=tk.W, padx=10, pady=5)

        client_frame = ttk.Frame(target_frame)
        client_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(client_frame, text="Select Client:").pack(side=tk.LEFT)
        self.notification_client_var = tk.StringVar()
        self.notification_client_combo = ttk.Combobox(client_frame, textvariable=self.notification_client_var, width=30)
        self.notification_client_combo.pack(side=tk.LEFT, padx=5)

        # Notification content
        content_frame = ttk.LabelFrame(notification_frame, text="Notification Content")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(content_frame, text="Message:").pack(anchor=tk.W, padx=10, pady=5)
        self.notification_message_text = scrolledtext.ScrolledText(content_frame, width=50, height=10, wrap=tk.WORD)
        self.notification_message_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Schedule frame
        schedule_frame = ttk.LabelFrame(notification_frame, text="Schedule Notification")
        schedule_frame.pack(fill=tk.X, padx=10, pady=10)

        self.schedule_notification_var = tk.BooleanVar(value=False)
        schedule_check = ttk.Checkbutton(schedule_frame, text="Schedule for later", variable=self.schedule_notification_var)
        schedule_check.pack(anchor=tk.W, padx=10, pady=5)

        schedule_time_frame = ttk.Frame(schedule_frame)
        schedule_time_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(schedule_time_frame, text="Date:").pack(side=tk.LEFT)
        self.schedule_date_entry = DateEntry(schedule_time_frame, width=12, background='darkblue', foreground='white', borderwidth=2)
        self.schedule_date_entry.pack(side=tk.LEFT, padx=5)

        ttk.Label(schedule_time_frame, text="Time:").pack(side=tk.LEFT, padx=5)

        self.schedule_hour_var = tk.StringVar()
        hour_spin = ttk.Spinbox(schedule_time_frame, from_=0, to=23, width=3, textvariable=self.schedule_hour_var)
        hour_spin.pack(side=tk.LEFT)

        ttk.Label(schedule_time_frame, text=":").pack(side=tk.LEFT)

        self.schedule_minute_var = tk.StringVar()
        minute_spin = ttk.Spinbox(schedule_time_frame, from_=0, to=59, width=3, textvariable=self.schedule_minute_var)
        minute_spin.pack(side=tk.LEFT)

        # Action buttons
        button_frame = ttk.Frame(notification_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Send Notification", command=self.send_notification).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear Form", command=self.clear_notification_form).pack(side=tk.LEFT, padx=5)

    def toggle_server(self):
        """Start or stop the server."""
        if self.server.running:
            self.server.stop()
            self.server_button.config(text="Start Server")
            self.status_var.set("Server stopped")
        else:
            success, message = self.server.start()
            if success:
                self.server_button.config(text="Stop Server")
                self.status_var.set(message)
                self.refresh_all()
            else:
                messagebox.showerror("Server Error", message)

    def periodic_refresh(self):
        """Periodically refresh the UI."""
        # Update the dashboard
        if self.server.running:
            self.refresh_dashboard()

        # Reschedule
        self.root.after(5000, self.periodic_refresh)

    def refresh_all(self):
        """Refresh all data tables."""
        self.refresh_dashboard()
        self.refresh_clients()
        self.refresh_tasks()
        self.update_client_combo_boxes()

    def refresh_dashboard(self):
        """Refresh the dashboard tab."""
        # Clear tables
        for item in self.dashboard_clients_table.get_children():
            self.dashboard_clients_table.delete(item)

        for item in self.dashboard_tasks_table.get_children():
            self.dashboard_tasks_table.delete(item)

        if not self.server.running:
            return

        # Add connected clients
        for client_id, client_info in self.server.clients.items():
            client = self.server.db.get_client(client_id)
            if client:
                self.dashboard_clients_table.insert("", tk.END, values=(
                    client_id,
                    client["name"],
                    "Connected"
                ))

        # Add pending tasks
        tasks = self.server.db.get_all_tasks()

        for task in tasks:
            if task["status"] != "Completed":
                tag = 'pending' if task["status"] == "Pending" else ''
                self.dashboard_tasks_table.insert("", tk.END, values=(
                    task["task_id"],
                    task["client_name"],
                    task["title"],
                    task["due_date"],
                    task["status"]
                ), tags=(tag,))

