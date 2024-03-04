import sys
import asyncio
import threading
import websockets
import time
import json
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QTextEdit, QListWidget
from PyQt5.QtCore import QObject, pyqtSignal,pyqtSlot
from DrissionPage import ChromiumPage



class WebSocketServer(QObject):
    client_connected = pyqtSignal(str)
    client_disconnected = pyqtSignal(str)
    message_received = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.clients = set()
        self.server = None
        self.thread = threading.Thread(target=self.start_server)
        self.running = threading.Event()

    def start_server(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        self.server = websockets.serve(self.handle_client, "0.0.0.0", 8765)
        asyncio.get_event_loop().run_until_complete(self.server)
        asyncio.get_event_loop().run_forever()

    async def handle_client(self, websocket, path):
        self.clients.add(websocket)
        self.client_connected.emit(str(websocket.remote_address))

        await websocket.send("""{"content":"已连接","nickName":"websocket服务"}""")


        try:
            async for message in websocket:
                self.message_received.emit(message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.remove(websocket)
            self.client_disconnected.emit(str(websocket.remote_address))

    def stop_server(self):
        if self.server:
            self.server.ws_server.close()
            self.thread.quit()
            self.running.clear()



    def send_message(self, message):
        for client in self.clients:
            asyncio.run(client.send(message))


class ContentFetcher(QObject):
    contentReceived = pyqtSignal(str)

    def __init__(self, interval=5):
        super().__init__()
        self._running = threading.Event()
        self._running.set()
        self.interval = interval
        # 创建页面对象，并启动或接管浏览器
        self.page = ChromiumPage()
        # 跳转到登录页面
        self.page.get('https://channels.weixin.qq.com/platform/login')

    def run(self):
        while self._running.is_set():
            # 在这里执行定时任务，获取连接地址中的特定内容
            content = "Special content from server"
            self.contentReceived.emit(content)
            time.sleep(self.interval)

    def pauseLoop(self):
        self._running.clear()

    def resumeLoop(self):
        self._running.set()

    def setInterval(self, interval):
        self.interval = interval

             

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WebSocket Server")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        self.start_button = QPushButton("Start Server")
        self.start_button.clicked.connect(self.start_server)
        layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Server")
        self.stop_button.clicked.connect(self.stop_server)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)

        self.message_edit = QTextEdit()
        layout.addWidget(self.message_edit)

        self.send_button = QPushButton("Send Message")
        self.send_button.clicked.connect(self.send_message)
        layout.addWidget(self.send_button)

        self.client_list = QListWidget()
        layout.addWidget(self.client_list)

        self.message_list = QListWidget()
        layout.addWidget(self.message_list)

        self.setLayout(layout)

        self.websocket_server = WebSocketServer()
        self.websocket_server.client_connected.connect(self.update_client_list)
        self.websocket_server.client_disconnected.connect(self.update_client_list)
        self.websocket_server.message_received.connect(self.update_message_list)

    def start_server(self):
        self.websocket_server.running.set()
        self.websocket_server.thread.start()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def stop_server(self):
        self.websocket_server.stop_server()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def send_message(self):
        content = self.message_edit.toPlainText()
        message = f"""{{"content":"{content}","nickName":"websocket服务"}}"""       
        if message:
            self.websocket_server.send_message(message)

    def update_client_list(self, address):
        if self.websocket_server.running.is_set():
            self.client_list.clear()
            for client in self.websocket_server.clients:
                self.client_list.addItem(str(client.remote_address))

    def update_message_list(self, message):
        if self.websocket_server.running.is_set():
            self.message_list.addItem(message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
