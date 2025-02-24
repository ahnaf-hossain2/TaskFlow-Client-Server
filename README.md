# TaskFlow Client-Server System

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Architecture](https://img.shields.io/badge/Architecture-Client%2FServer-orange)

A robust task management system with a server-side admin panel and client applications. Features real-time updates, system tray integration, and desktop notifications.

![Demo](![python_tpqUHss2Av](https://github.com/user-attachments/assets/ffea7a7b-a68d-4d33-a0ef-c512cb21737e)
)

## Features

### Server (Admin Panel)
📊 **Client Management**
✅ Add/remove clients
🖥️ Track connected clients

📋 **Task Management**
➕ Assign tasks with due dates
🔄 Update task statuses in real-time
🗑️ Delete tasks

🔔 **Notifications**
📨 Broadcast messages to all clients
📩 Send targeted notifications

### Client Application
📥 **Real-Time Updates**
🔄 Sync tasks and notifications instantly

🗔 **System Tray Integration**
➖ Minimize to tray
🔔 Tray notifications for new tasks

📝 **Task Actions**
✔️ Mark tasks as Completed/In Progress

## Prerequisites

- Python 3.9+
- PIP package manager

## Installation

1. **Clone Repository**
   ```bash
   git clone https://github.com/yourusername/TaskFlow-Client-Server.git
   cd TaskFlow-Client-Server

2. **Install Deoendencies**
   ```bash
   pip install -r requirements.txt

## Usage

1. **Start Server**
  ```bash
  python server.py

*First-run configuration window will appear
*Default: 127.0.0.1:5000

2. **Start Client**
    ```python client.py

*Enter client ID on first launch
*Runs in system tray after login

## Project Structure

TaskFlow-Client-Server/
├── server.py            # Admin panel + server logic
├── client.py            # Client application
├── icon.png             # Tray icon
├── requirements.txt
├── LICENSE
└── README.md

## Contributing

1. For the repository
2. Create feature branch (git checkout -b feature/foo)
3. Commit changes (git commit -am 'Add foo')
4. Push to branch (git push origin feature/foo)
5. Open Pull Request

## License

Distribute uder the MIT License. See LICENSE for details.
If this repo is helpful to you then please consider giving it a star ⭐
