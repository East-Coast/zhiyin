import sys
import asyncio
import threading
import websockets
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel, QLineEdit, QTextEdit
from apscheduler.schedulers.asyncio import AsyncIOScheduler

class WebSocketThread(threading.Thread):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.websocket = None
        self.connected_devices = set()
        self.messages = []
        self.is_running = False

    async def handle_client(self, websocket, path):
        self.websocket = websocket
        self.connected_devices.add(websocket.remote_address)
        self.update_device_list()
        self.is_running = True
        async for message in websocket:
            print(f"Received message: {message}")
            self.messages.append(message)
            self.window.update_messages()

    def run(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        start_server = websockets.serve(self.handle_client, "localhost", 8765)
        asyncio.get_event_loop().run_until_complete(start_server)
        self.is_running = True
        asyncio.get_event_loop().run_forever()

    async def send_message(self, message):
        if self.websocket:
            await self.websocket.send(message)

    def update_device_list(self):
        self.window.update_device_list(list(self.connected_devices))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("WebSocket 示例")
        self.setGeometry(100, 100, 400, 500)

        layout = QVBoxLayout()
        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)

        self.start_button = QPushButton("启动 WebSocket 服务器")
        self.start_button.clicked.connect(self.start_server)
        layout.addWidget(self.start_button)

        self.server_status_label = QLabel("WebSocket 服务器状态: 未启动")
        layout.addWidget(self.server_status_label)

        self.device_label = QLabel("连接设备: ")
        layout.addWidget(self.device_label)

        self.messages_label = QLabel("接收到的消息:")
        layout.addWidget(self.messages_label)

        self.messages_text = QTextEdit()
        layout.addWidget(self.messages_text)

        self.message_input = QLineEdit()
        layout.addWidget(self.message_input)

        self.send_button = QPushButton("发送消息")
        self.send_button.clicked.connect(self.send_message)
        layout.addWidget(self.send_button)

        self.interval_label = QLabel("定时间隔（秒）:")
        layout.addWidget(self.interval_label)

        self.interval_input = QLineEdit()
        layout.addWidget(self.interval_input)

        self.start_timer_button = QPushButton("开启定时任务")
        self.start_timer_button.clicked.connect(self.start_timer)
        layout.addWidget(self.start_timer_button)

        self.websocket_thread = None
        self.scheduler = AsyncIOScheduler()
        self.scheduler.start()

    def start_server(self):
        self.websocket_thread = WebSocketThread(self)
        self.websocket_thread.start()
        self.server_status_label.setText("WebSocket 服务器状态: 运行中")

    def send_message(self):
        message = self.message_input.text()
        if message and self.websocket_thread:
            asyncio.run(self.websocket_thread.send_message(message))
            self.message_input.clear()

    def update_messages(self):
        messages = "\n".join(self.websocket_thread.messages)
        self.messages_text.setPlainText(messages)

    def update_device_list(self, devices):
        device_text = ", ".join(str(device) for device in devices)
        self.device_label.setText(f"连接设备: {device_text}")

    def start_timer(self):
        interval_str = self.interval_input.text()
        if interval_str and self.websocket_thread:
            interval = float(interval_str)
            if not self.scheduler.get_job("send_message"):
                self.scheduler.add_job(self.send_periodic_message, "interval", seconds=interval, id="send_message")
                self.start_timer_button.setText("取消定时任务")
            else:
                self.scheduler.remove_job("send_message")
                self.start_timer_button.setText("开启定时任务")

    async def send_periodic_message(self):
        message = "定时任务：发送消息"
        if self.websocket_thread:
            await self.websocket_thread.send_message(message)

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
