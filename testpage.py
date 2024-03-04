import sys
import asyncio
import threading
import websockets
import time
import datetime
import random
import json
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QPushButton, QTextEdit, QListWidget, QWidget , QHBoxLayout,QLabel
from PySide6.QtCore import QObject, Signal, Slot, Qt
from DrissionPage import ChromiumPage  # Assuming this is an external module
import qrcode
import socket
from PIL import ImageQt
from PySide6.QtGui import QPixmap


class WebSocketServer(QObject):
    client_connected = Signal(str)
    client_disconnected = Signal(str)
    message_received = Signal(str)

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
            self.running.clear()

    def send_message(self, message):
        for client in self.clients:
            asyncio.run(client.send(message))


class ContentFetcher(QObject):
    contentReceived = Signal(str)

    def __init__(self, interval=1):
        super().__init__()
        self._running = threading.Event()
        self._running.set()
        self.interval = interval
        self.comment_list = []

        # 记录每个键的上一次回复时间
        self.last_reply_time = {}

        # 自动回复设置
        self.reply_data = {
            "这是什么&1": ["海里生海里长的小动物，马粪海胆"],
            "公&母&2": ["海胆黄颜色比较深的是母海胆，海胆黄发白浅色的是公海胆"],
            "怎么吃&3": ["海胆黄是可以直接吃的",
                    "拌面拌饭，炒饭炒面，包个包子、饺子都是可以的"],
        }


        # 创建页面对象，并启动或接管浏览器
        self.page = ChromiumPage()  # Assuming this is an external module
        # 跳转到登录页面
        self.page.get('https://channels.weixin.qq.com/platform/live/liveBuild')

    def run(self):
        while self._running.is_set():
            # 在这里执行定时任务，获取连接地址中的特定内容
            # content = "Special content from server"
            # self.contentReceived.emit(content)
            self.print_comment()
            time.sleep(self.interval)

    

    def match_and_reply(self,input_str):
        now = datetime.datetime.now()
        
        # 遍历数据中的每个键
        for key in self.reply_data.keys():
            # 将键按照"&"分割成数组
            key_elements = key.split('&')

            # 检查输入字符串是否包含键数组中的任何一个元素
            if any(elem in input_str for elem in key_elements):
                # 检查是否在过去30秒内已经回复过
                if key in self.last_reply_time and (now - self.last_reply_time[key]).total_seconds() < 5:
                    continue

                # 更新回复时间
                self.last_reply_time[key] = now
                # 如果匹配，从对应的回复列表中随机选择一个回复
                return random.choice(self.reply_data[key])

        # 如果没有找到匹配项，可以返回默认回复或者None
        return None

    def get_subarray_after_value(self,arr, value):
        try:
            index = arr.index(value)  # 查找传入值在数组中的位置
            return arr[index+1:]  # 返回从该位置之后的元素数组
        except ValueError:
            return arr[:]  # 如果数组不包含传入的值，则返回整个数组

    
    # 实时获取评论数据
    def print_comment(self):
        
        eles = self.page.eles('@class=live-message-item')
        commentItem_list = eles
        if len(self.comment_list) > 0 :
            commentItem_list = self.get_subarray_after_value(eles,self.comment_list[-1])
        
        
        for item in commentItem_list[len(self.comment_list):]:
            
            nicknameEle = item.ele('@class=message-username-desc')
            descriptionEle = item.ele('@class=message-content')

            if nicknameEle and descriptionEle :
                message = f"""{{"content":"{descriptionEle.text}","nickName":"{nicknameEle.text}"}}"""
                self.contentReceived.emit(message)

        self.comment_list = commentItem_list.copy()

    def pauseLoop(self):
        self._running.clear()

    def resumeLoop(self):
        self._running.set()

    def setInterval(self, interval):
        self.interval = interval


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WebSocket Server")
        self.init_ui()
        

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout()

        left_layout = QVBoxLayout()
        self.start_fetch_button = QPushButton("Start Fetching")
        self.start_fetch_button.clicked.connect(self.start_fetching)
        left_layout.addWidget(self.start_fetch_button)
        self.fetch_result_text = QListWidget()
        left_layout.addWidget(self.fetch_result_text)
        main_layout.addLayout(left_layout)

        right_layout = QVBoxLayout()

        # 创建用于显示二维码的标签
        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignCenter)  # 设置标签内容居中对齐
        self.qr_label.setFixedSize(100, 100)
        right_layout.addWidget(self.qr_label)

        self.start_button = QPushButton("Start Server")
        self.start_button.clicked.connect(self.start_server)
        right_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Server")
        self.stop_button.clicked.connect(self.stop_server)
        self.stop_button.setEnabled(False)
        right_layout.addWidget(self.stop_button)

        self.message_edit = QTextEdit()
        right_layout.addWidget(self.message_edit)

        self.send_button = QPushButton("Send Message")
        self.send_button.clicked.connect(self.send_message)
        right_layout.addWidget(self.send_button)

        self.client_list = QListWidget()
        right_layout.addWidget(self.client_list)

        self.message_list = QListWidget()
        right_layout.addWidget(self.message_list)

        main_layout.addLayout(right_layout)

        central_widget.setLayout(main_layout)

        self.websocket_server = WebSocketServer()
        self.websocket_server.client_connected.connect(self.update_client_list)
        self.websocket_server.client_disconnected.connect(self.update_client_list)
        self.websocket_server.message_received.connect(self.update_message_list)

    def start_fetching(self):
        def run_content_fetcher():
            self.content_fetcher = ContentFetcher()
            self.content_fetcher.contentReceived.connect(self.display_fetch_result)
            self.content_fetcher.run()

        # Create a thread to run the content fetcher
        self.fetch_thread = threading.Thread(target=run_content_fetcher)
        self.fetch_thread.start()

    def display_fetch_result(self, content):
        self.fetch_result_text.addItem(content)
        self.websocket_server.send_message(content)


    def start_server(self):
        self.get_qr_code()
        self.websocket_server.running.set()
        self.websocket_server.thread.start()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def stop_server(self):
        self.websocket_server.stop_server()
        self.websocket_server.quit()
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

     
    def get_qr_code(self):
        # 获取当前主机的IP地址
        ip_address = "ws://" + self.get_ip_address() + ":8765"

        # 生成二维码
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(ip_address)
        qr.make(fit=True)

        # 创建二维码图像
        img = qr.make_image(fill_color="black", back_color="white")

        # 将PIL图像转换为Qt图像
        qt_img = ImageQt.ImageQt(img)

        # 将Qt图像转换为QPixmap
        pixmap = QPixmap.fromImage(qt_img)

        # 在标签上显示二维码
        self.qr_label.setPixmap(pixmap)
        self.qr_label.setScaledContents(True)

    def get_ip_address(self):
        try:
            # 创建一个套接字连接到互联网
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))  # 连接到Google的DNS服务器
            ip_address = s.getsockname()[0]  # 获取套接字的本地地址
            s.close()
            return ip_address
        except socket.error:
            return "无法获取IP地址"


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
