import socket
import threading
import json
import tkinter as tk
from tkinter import ttk, messagebox
import os
import pickle
from ttkthemes import ThemedTk
import time
from PIL import Image, ImageTk
import sys
from datetime import datetime

class TaskClient:
    def __init__(self, host='127.0.0.1', port=5555):
        self.host = host
        self.port = port
        self.sock = None
        self.client_id = None
        self.client_name = None
        self.connected = False
        self.tasks = {}  # {task_id: task_data}

        # Event for connection status
        self.connection_event = threading.Event()

        # Callbacks - will be set by GUI
        self.on_new_task = None
        self.on_task_update = None
        self.on_task_removed = None
        self.on_notification = None
        self.on_connection_lost = None

    def connect(self, client_id):
        """Connect to the server."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)  # 5 second timeout for connection
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(None)  # Reset timeout

            # Send login data
            self.send_message({
                "type": "login",
                "client_id": client_id
            })

            # Receive login response
            response = self.receive_message()

            if response and response.get("type") == "login_response":
                if response.get("status") == "success":
                    self.client_id = client_id
                    self.client_name = response.get("name", "Unknown")
                    self.connected = True

                    # Start listening for messages from the server
                    self.listen_thread = threading.Thread(target=self.listen_for_messages)
                    self.listen_thread.daemon = True
                    self.listen_thread.start()

                    # Save client ID for auto-login
                    self.save_client_id()

                    # Set connection event
                    self.connection_event.set()

                    return True, "Connected successfully as " + self.client_name
                else:
                    self.sock.close()
                    return False, response.get("message", "Login failed")
            else:
                self.sock.close()
                return False, "Invalid response from server"

        except socket.timeout:
            if self.sock:
                self.sock.close()
            return False, "Connection timed out"
        except ConnectionRefusedError:
            if self.sock:
                self.sock.close()
            return False, "Server is not running"
        except Exception as e:
            if self.sock:
                self.sock.close()
            return False, f"Connection error: {str(e)}"

    def disconnect(self):
        """Disconnect from the server."""
        self.connected = False
        if self.sock:
            self.sock.close()

    def listen_for_messages(self):
        """Listen for messages from the server."""
        while self.connected:
            try:
                message = self.receive_message()

                if not message:
                    self.handle_connection_lost()
                    break

                self.handle_message(message)

            except Exception as e:
                if self.connected:
                    self.handle_connection_lost()
                break

    def handle_message(self, message):
        """Handle a message received from the server."""
        msg_type = message.get("type")

        if msg_type == "task_list":
            # Initial task list
            tasks = message.get("tasks", [])
            for task in tasks:
                task_id = task.get("task_id")
                self.tasks[task_id] = task

            # Notify GUI
            if self.on_task_update:
                self.on_task_update()

        elif msg_type == "new_task":
            # New task assigned
            task_id = message.get("task_id")
            self.tasks[task_id] = message

            # Notify GUI
            if self.on_new_task:
                self.on_new_task(message)

        elif msg_type == "task_updated":
            # Task updated
            task_id = message.get("task_id")
            self.tasks[task_id] = message

            # Notify GUI
            if self.on_task_update:
                self.on_task_update()

        elif msg_type == "task_removed":
            # Task removed
            task_id = message.get("task_id")
            if task_id in self.tasks:
                del self.tasks[task_id]

            # Notify GUI
            if self.on_task_removed:
                self.on_task_removed(task_id)

        elif msg_type == "notification":
            # Notification from server
            if self.on_notification:
                self.on_notification(message.get("message", ""))

        elif msg_type == "server_shutdown":
            # Server is shutting down
            self.handle_connection_lost("Server has been shut down")

        elif msg_type == "account_deactivated":
            # Account deactivated
            self.handle_connection_lost("Your account has been deactivated")
            # Remove saved client ID
            self.remove_saved_client_id()

        elif msg_type == "account_deleted":
            # Account deleted
            self.handle_connection_lost("Your account has been deleted")
            # Remove saved client ID
            self.remove_saved_client_id()

    def handle_connection_lost(self, message="Connection to server lost"):
        """Handle lost connection to server."""
        if self.connected:
            self.connected = False
            if self.sock:
                self.sock.close()

            # Notify GUI
            if self.on_connection_lost:
                self.on_connection_lost(message)

    def update_task_status(self, task_id, status):
        """Update task status on the server."""
        if not self.connected:
            return False

        try:
            self.send_message({
                "type": "task_update",
                "task_id": task_id,
                "status": status
            })

            # Update local task
            if task_id in self.tasks:
                self.tasks[task_id]["status"] = status

            return True
        except:
            self.handle_connection_lost()
            return False

    def send_message(self, message):
        """Send a message to the server."""
        try:
            message_json = json.dumps(message)
            message_bytes = message_json.encode('utf-8')
            length = len(message_bytes)
            length_bytes = length.to_bytes(4, byteorder='big')
            self.sock.sendall(length_bytes + message_bytes)
            return True
        except:
            raise

    def receive_message(self):
        """Receive a message from the server."""
        try:
            # Receive message length (4 bytes)
            length_bytes = self.sock.recv(4)
            if not length_bytes:
                return None

            length = int.from_bytes(length_bytes, byteorder='big')

            # Receive data
            data = b''
            while len(data) < length:
                packet = self.sock.recv(min(length - len(data), 4096))
                if not packet:
                    return None
                data += packet

            # Decode and parse
            message_json = data.decode('utf-8')
            message = json.loads(message_json)

            return message
        except:
            raise

    def save_client_id(self):
        """Save client ID for auto-login."""
        try:
            with open("client_config.dat", "wb") as f:
                pickle.dump(self.client_id, f)
        except:
            pass

    def load_saved_client_id(self):
        """Load saved client ID for auto-login."""
        try:
            if os.path.exists("client_config.dat"):
                with open("client_config.dat", "rb") as f:
                    return pickle.load(f)
        except:
            pass
        return None

    def remove_saved_client_id(self):
        """Remove saved client ID."""
        try:
            if os.path.exists("client_config.dat"):
                os.remove("client_config.dat")
        except:
            pass

class SystemTrayIcon:
    """System tray icon for notifications."""
    def __init__(self, icon_path, hover_text):
        try:
            import pystray
            from PIL import Image

            self.icon = pystray.Icon("task_client")
            self.icon.icon = Image.open(icon_path)
            self.icon.title = hover_text

            self.menu = pystray.Menu(
                pystray.MenuItem("Show", self.show_window),
                pystray.MenuItem("Exit", self.exit_app)
            )

            self.icon.menu = self.menu

            # Set callbacks
            self.on_show = None
            self.on_exit = None

            # Start icon in separate thread
            threading.Thread(target=self.icon.run, daemon=True).start()

            self.supported = True
        except:
            self.supported = False

    def show_window(self):
        """Show the main window."""
        if self.on_show:
            self.on_show()

    def exit_app(self):
        """Exit the application."""
        if self.on_exit:
            self.on_exit()

    def show_notification(self, title, message):
        """Show a system tray notification."""
        if self.supported:
            self.icon.notify(message, title)

class ClientGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Task Manager - Client")
        self.root.geometry("900x600")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Initialize client
        self.client = TaskClient()

        # Set client callbacks
        self.client.on_new_task = self.handle_new_task
        self.client.on_task_update = self.refresh_tasks
        self.client.on_task_removed = self.handle_task_removed
        self.client.on_notification = self.handle_notification
        self.client.on_connection_lost = self.handle_connection_lost

        # Initialize system tray icon
        self.setup_system_tray()

        # Check if already logged in
        saved_client_id = self.client.load_saved_client_id()
        if saved_client_id:
            self.show_main_interface()
            # Try to connect with saved ID in background
            threading.Thread(target=self.connect_with_saved_id, args=(saved_client_id,), daemon=True).start()
        else:
            self.show_login_interface()

    def setup_system_tray(self):
        """Setup system tray icon for notifications."""
        # Create a default icon file if it doesn't exist
        icon_path = "task_icon.png"
        if not os.path.exists(icon_path):
            self.create_default_icon(icon_path)

        self.tray_icon = SystemTrayIcon(icon_path, "Task Manager")
        self.tray_icon.on_show = self.show_window
        self.tray_icon.on_exit = self.exit_app

    def create_default_icon(self, path):
        """Create a default icon file."""
        try:
            # Create a simple colored square
            img = Image.new('RGB', (64, 64), color='blue')
            img.save(path)
        except:
            pass

    def show_window(self):
        """Show the main window."""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def exit_app(self):
        """Exit the application."""
        self.on_close(force_exit=True)

    def show_login_interface(self):
        """Show the login interface."""
        # Clear current widgets
        for widget in self.root.winfo_children():
            widget.destroy()

        # Create login frame
        login_frame = ttk.Frame(self.root, padding=20)
        login_frame.pack(expand=True)

        # Title
        title_label = ttk.Label(login_frame, text="Task Manager Client", font=("TkDefaultFont", 16, "bold"))
        title_label.pack(pady=10)

        # Client ID entry
        ttk.Label(login_frame, text="Enter your Client ID:").pack(pady=(20, 5))

        self.client_id_var = tk.StringVar()
        client_id_entry = ttk.Entry(login_frame, textvariable=self.client_id_var, width=30)
        client_id_entry.pack(pady=5)
        client_id_entry.focus()

        # Server settings
        settings_frame = ttk.LabelFrame(login_frame, text="Server Settings")
        settings_frame.pack(pady=15, fill=tk.X)

        ttk.Label(settings_frame, text="Server IP:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.server_ip_var = tk.StringVar(value=self.client.host)
        ttk.Entry(settings_frame, textvariable=self.server_ip_var, width=15).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(settings_frame, text="Port:").grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
        self.server_port_var = tk.StringVar(value=str(self.client.port))
        ttk.Entry(settings_frame, textvariable=self.server_port_var, width=6).grid(row=0, column=3, padx=5, pady=5)

        # Status label
        self.status_label = ttk.Label(login_frame, text="")
        self.status_label.pack(pady=10)

        # Connect button
        self.connect_button = ttk.Button(login_frame, text="Connect", command=self.connect_to_server)
        self.connect_button.pack(pady=5)

        # Bind Enter key to connect
        client_id_entry.bind("<Return>", lambda event: self.connect_to_server())

    def connect_to_server(self):
        """Connect to the server with the provided client ID."""
        client_id = self.client_id_var.get().strip()

        if not client_id:
            self.status_label.config(text="Please enter a Client ID", foreground="red")
            return

        # Update server settings
        try:
            self.client.host = self.server_ip_var.get().strip()
            self.client.port = int(self.server_port_var.get().strip())
        except:
            self.status_label.config(text="Invalid port number", foreground="red")
            return

        # Disable connect button
        self.connect_button.config(state=tk.DISABLED)
        self.status_label.config(text="Connecting...", foreground="black")

        # Connect in a separate thread
        threading.Thread(target=self.connect_thread, args=(client_id,), daemon=True).start()

    def connect_thread(self, client_id):
        """Thread function for connecting to server."""
        success, message = self.client.connect(client_id)

        if success:
            # Switch to main interface
            self.root.after(0, self.show_main_interface)
        else:
            # Show error message
            self.root.after(0, lambda: self.status_label.config(text=message, foreground="red"))
            self.root.after(0, lambda: self.connect_button.config(state=tk.NORMAL))

    def connect_with_saved_id(self, client_id):
        """Connect with saved client ID."""
        success, message = self.client.connect(client_id)

        if success:
            # Update GUI
            self.root.after(0, self.update_connection_status)
            self.root.after(0, self.refresh_tasks)
        else:
            # Show login interface
            self.root.after(0, self.show_login_interface)
            self.root.after(0, lambda: self.status_label.config(text=message, foreground="red"))

    def show_main_interface(self):
        """Show the main task interface."""
        # Clear current widgets
        for widget in self.root.winfo_children():
            widget.destroy()

        # Create main frame
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header frame
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        # Client info
        info_frame = ttk.Frame(header_frame)
        info_frame.pack(side=tk.LEFT)

        self.client_name_label = ttk.Label(info_frame, text="", font=("TkDefaultFont", 12, "bold"))
        self.client_name_label.pack(anchor=tk.W)

        self.connection_status_label = ttk.Label(info_frame, text="Status: Connecting...")
        self.connection_status_label.pack(anchor=tk.W)

        # Refresh button
        refresh_btn = ttk.Button(header_frame, text="Refresh Tasks", command=self.refresh_tasks)
        refresh_btn.pack(side=tk.RIGHT)

        # Tasks frame
        tasks_frame = ttk.LabelFrame(main_frame, text="My Tasks")
        tasks_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Tasks tree
        columns = ("title", "description", "due_date", "status")
        self.tasks_tree = ttk.Treeview(tasks_frame, columns=columns, show="headings")

        self.tasks_tree.heading("title", text="Title")
        self.tasks_tree.heading("description", text="Description")
        self.tasks_tree.heading("due_date", text="Due Date")
        self.tasks_tree.heading("status", text="Status")

        self.tasks_tree.column("title", width=150, minwidth=100)
        self.tasks_tree.column("description", width=300, minwidth=150)
        self.tasks_tree.column("due_date", width=100, minwidth=100)
        self.tasks_tree.column("status", width=100, minwidth=80)

        # Scrollbars
        vsb = ttk.Scrollbar(tasks_frame, orient=tk.VERTICAL, command=self.tasks_tree.yview)
        hsb = ttk.Scrollbar(tasks_frame, orient=tk.HORIZONTAL, command=self.tasks_tree.xview)
        self.tasks_tree.configure(yscroll=vsb.set, xscroll=hsb.set)

        self.tasks_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        # Task details frame
        details_frame = ttk.LabelFrame(main_frame, text="Task Details")
        details_frame.pack(fill=tk.BOTH, pady=10)

        # Details
        details_inner_frame = ttk.Frame(details_frame)
        details_inner_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(details_inner_frame, text="Title:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.task_title_label = ttk.Label(details_inner_frame, text="", font=("TkDefaultFont", 10, "bold"))
        self.task_title_label.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(details_inner_frame, text="Description:").grid(row=1, column=0, sticky=tk.NW, padx=5, pady=2)
        self.task_desc_label = ttk.Label(details_inner_frame, text="", wraplength=400)
        self.task_desc_label.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(details_inner_frame, text="Due Date:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.task_due_label = ttk.Label(details_inner_frame, text="")
        self.task_due_label.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(details_inner_frame, text="Status:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)

        # Status frame with combobox and update button
        status_frame = ttk.Frame(details_inner_frame)
        status_frame.grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)

        self.task_status_var = tk.StringVar()
        self.task_status_combo = ttk.Combobox(status_frame, textvariable=self.task_status_var,
                                             values=["Pending", "In Progress", "Completed"],
                                             state="readonly", width=15)
        self.task_status_combo.pack(side=tk.LEFT, padx=(0, 10))

        self.update_status_btn = ttk.Button(status_frame, text="Update Status",
                                           command=self.update_task_status)
        self.update_status_btn.pack(side=tk.LEFT)

        # Bind task selection
        self.tasks_tree.bind("<<TreeviewSelect>>", self.on_task_select)

        # Update interface with client information
        if self.client.connected:
            self.update_connection_status()

        # Selected task ID
        self.selected_task_id = None

    def update_connection_status(self):
        """Update connection status display."""
        if hasattr(self, 'client_name_label'):
            self.client_name_label.config(text=f"Welcome, {self.client.client_name}")

        if hasattr(self, 'connection_status_label'):
            if self.client.connected:
                self.connection_status_label.config(text="Status: Connected", foreground="green")
            else:
                self.connection_status_label.config(text="Status: Disconnected", foreground="red")

    def refresh_tasks(self):
        """Refresh the tasks tree."""
        if not hasattr(self, 'tasks_tree'):
            return

        # Clear tree
        for item in self.tasks_tree.get_children():
            self.tasks_tree.delete(item)

        # Add tasks
        for task_id, task in self.client.tasks.items():
            self.tasks_tree.insert("", tk.END, iid=str(task_id), values=(
                task.get("title", ""),
                task.get("description", ""),
                task.get("due_date", ""),
                task.get("status", "")
            ))

        # Clear selection
        self.clear_task_details()

    def clear_task_details(self):
        """Clear task details display."""
        self.task_title_label.config(text="")
        self.task_desc_label.config(text="")
        self.task_due_label.config(text="")
        self.task_status_var.set("")
        self.update_status_btn.config(state=tk.DISABLED)
        self.selected_task_id = None

    def on_task_select(self, event):
        """Handle task selection in the tree."""
        selected_items = self.tasks_tree.selection()
        if not selected_items:
            self.clear_task_details()
            return

        # Get task ID
        task_id = int(selected_items[0])
        self.selected_task_id = task_id

        # Get task details
        task = self.client.tasks.get(task_id)
        if not task:
            self.clear_task_details()
            return

        # Update details display
        self.task_title_label.config(text=task.get("title", ""))
        self.task_desc_label.config(text=task.get("description", ""))
        self.task_due_label.config(text=task.get("due_date", ""))
        self.task_status_var.set(task.get("status", ""))

        # Enable update button
        self.update_status_btn.config(state=tk.NORMAL)

    def update_task_status(self):
        """Update task status on the server."""
        if not self.selected_task_id or not self.client.connected:
            return

        new_status = self.task_status_var.get()
        if not new_status:
            return

        # Update on server
        success = self.client.update_task_status(self.selected_task_id, new_status)

        if success:
            # Update in tree
            self.tasks_tree.item(str(self.selected_task_id),
                                values=(
                                    self.client.tasks[self.selected_task_id].get("title", ""),
                                    self.client.tasks[self.selected_task_id].get("description", ""),
                                    self.client.tasks[self.selected_task_id].get("due_date", ""),
                                    new_status
                                ))
        else:
            messagebox.showerror("Error", "Failed to update task status")

    def handle_new_task(self, task):
        """Handle new task notification."""
        # Add to tree if view is available
        if hasattr(self, 'tasks_tree'):
            self.tasks_tree.insert("", tk.END, iid=str(task.get("task_id")), values=(
                task.get("title", ""),
                task.get("description", ""),
                task.get("due_date", ""),
                task.get("status", "")
            ))

        # Show notification
        title = "New Task Assigned"
        message = f"Task: {task.get('title')}"

        # Show system tray notification
        if self.tray_icon.supported:
            self.tray_icon.show_notification(title, message)
        else:
            # Fallback to messagebox if system tray not supported
            if not self.root.winfo_viewable():
                messagebox.showinfo(title, message)

    def handle_task_removed(self, task_id):
        """Handle task removal notification."""
        # Remove from tree if view is available
        if hasattr(self, 'tasks_tree'):
            try:
                self.tasks_tree.delete(str(task_id))
            except:
                pass

            # Clear details if selected
            if self.selected_task_id == task_id:
                self.clear_task_details()

    def handle_notification(self, message):
        """Handle notification from server."""
        # Show system tray notification
        if self.tray_icon.supported:
            self.tray_icon.show_notification("Notification", message)
        else:
            # Fallback to messagebox if system tray not supported
            if not self.root.winfo_viewable():
                messagebox.showinfo("Notification", message)
            else:
                messagebox.showinfo("Notification", message)

    def handle_connection_lost(self, message):
        """Handle lost connection to server."""
        # Update status
        self.update_connection_status()

        # Show message box
        messagebox.showerror("Connection Lost", message)

        # If account related, go back to login
        if "account" in message.lower():
            self.show_login_interface()

    def on_close(self, force_exit=False):
        """Handle window close event."""
        if not force_exit:
            # Minimize to system tray if supported
            if self.tray_icon.supported:
                self.root.withdraw()
                return

        # Disconnect client
        if self.client.connected:
            self.client.disconnect()

        # Exit application
        self.root.quit()
        sys.exit()

if __name__ == "__main__":
    # Create themed Tk root
    root = ThemedTk(theme="arc")  # Use a modern theme

    # Create client GUI
    app = ClientGUI(root)

    # Start main loop
    root.mainloop()
