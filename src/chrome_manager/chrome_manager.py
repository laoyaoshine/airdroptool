import asyncio
import os
import logging
import tkinter as tk
from tkinter import messagebox, ttk, simpledialog
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from ..core.fingerprint import generate_fingerprint
from ..core.proxy_manager import ProxyManager
from ..core.tools import log, handle_error
import psutil
import time
import pyautogui
import win32gui
import win32con
import win32com.client
import threading
from selenium.webdriver.common.keys import Keys
from pynput import mouse, keyboard
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
import queue
import requests
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# 设置日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 获取当前脚本所在的目录
current_dir = os.path.dirname(os.path.abspath(__file__))
icon_dir = os.path.join(current_dir, "..", "icon")

class ChromeManager:
    def __init__(self, num_instances: int = 5):
        self.num_instances = min(num_instances, 25)
        self.proxy_manager = ProxyManager()
        self.instances = {}
        self.selected_instances = []
        self.sync_active = True
        self.check_system_resources()
        self.last_click_time = 0
        self.click_debounce_interval = 0.5
        self.last_click_pos = None
        self.mouse_listener = None
        self.keyboard_listener = None
        self.mouse_pressed = False
        self.mouse_pressed_button = None
        self.event_queue = queue.Queue()
        self.last_released_keys = set()  # 用于跟踪已释放的按键，避免重复
        self.last_click_position = None  # 用于跟踪上一个点击位置
        self.special_keys = {
            'ctrl': 'Control',
            'shift': 'Shift',
            'alt': 'Alt',
            'backspace': 'Backspace',
            'enter': 'Enter',
            # 添加其他特殊按键的映射
        }
        self.last_pressed_state = False
        self.last_pressed_key = None
        self.current_instance = None  # 用于存储当前活动实例

    def check_system_resources(self):
        cpu_usage = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        if cpu_usage > 80 or memory.percent > 90:
            log("Warning: System resources are low (CPU > 80% or Memory > 90%). Limiting instances.")
            self.num_instances = min(self.num_instances, 2)

    def validate_proxy(self, proxy: str) -> bool:
        """验证代理是否有效"""
        try:
            proxies = {
                "http": f"http://{proxy}",
                "https": f"https://{proxy}",
            }
            response = requests.get("https://www.google.com", proxies=proxies, timeout=5)
            return response.status_code == 200
        except Exception as e:
            log(f"Proxy {proxy} validation failed: {e}")
            return False

    async def start_instances(self, batch_open_urls: list = None):
        proxy_file = "proxies.csv"
        if not os.path.exists(proxy_file):
            log(f"Proxy file '{proxy_file}' not found. Starting without proxies.")
            await self.start_instances_without_proxy(batch_open_urls)
        else:
            await self.proxy_manager.batch_import_proxies(proxy_file)
            if not self.proxy_manager.proxies:
                log("No valid proxies available. Starting without proxies.")
                await self.start_instances_without_proxy(batch_open_urls)
            else:
                valid_proxies = [proxy for proxy in self.proxy_manager.proxies if self.validate_proxy(proxy)]
                if not valid_proxies:
                    log("No valid proxies after validation. Starting without proxies.")
                    await self.start_instances_without_proxy(batch_open_urls)
                else:
                    await self.start_instances_with_proxy(valid_proxies, batch_open_urls)

    async def start_instances_without_proxy(self, batch_open_urls: list = None):
        tasks = []
        try:
            for i in range(self.num_instances):
                options = webdriver.ChromeOptions()
                options.add_argument("--no-first-run")
                options.add_argument("--no-default-browser-check")
                options.add_argument("--ignore-certificate-errors")
                options.add_argument("--ignore-ssl-errors")
                options.add_argument("--allow-insecure-localhost")
                options.add_argument("--disable-web-security")
                options.add_argument("--disable-extensions")
                options.add_argument("--disable-gpu")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--allow-running-insecure-content")
                options.add_argument("--ignore-certificate-errors-spki-list")
                options.add_experimental_option("excludeSwitches", ["enable-logging"])
                options.add_argument("--disable-background-networking")
                options.add_argument("--disable-sync")
                port = 9222 + i
                options.add_argument(f"--remote-debugging-port={port}")
                user_data_dir = os.path.join(current_dir, f"profile_no_proxy_{i}_{int(time.time())}")
                options.add_argument(f"user-data-dir={user_data_dir}")

                service = Service(ChromeDriverManager().install())
                service.start_timeout = 30
                
                try:
                    driver = webdriver.Chrome(service=service, options=options)
                    driver.get("about:blank")
                except Exception as e:
                    log(f"Failed to start Chrome instance {i} on port {port}: {e}")
                    continue
                
                time.sleep(3)
                
                hwnd = self.get_chrome_window_handle(driver)
                if hwnd:
                    self.instances[i] = {"driver": driver, "proxy": None, "user_data_dir": user_data_dir, "hwnd": hwnd, "port": port}
                    log(f"Started instance {i} without proxy on port {port}")
                else:
                    log(f"Failed to get window handle for instance {i}, skipping...")
                    driver.quit()
                    continue
                
                if batch_open_urls:
                    for url in batch_open_urls:
                        driver.get(url)
                        log(f"Opened URL {url} in instance {i}")
                
                tasks.append(asyncio.sleep(1))
            
            await asyncio.gather(*tasks)
            self.arrange_windows()
        except Exception as e:
            handle_error(e, "Starting Chrome instances without proxy")

    async def start_instances_with_proxy(self, valid_proxies: list, batch_open_urls: list = None):
        tasks = []
        try:
            for i in range(min(self.num_instances, len(valid_proxies))):
                proxy = valid_proxies[i % len(valid_proxies)]
                options = webdriver.ChromeOptions()
                options.add_argument(f"--proxy-server={proxy}")
                options.add_argument("--start-maximized")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-gpu")
                options.add_argument("--disable-infobars")
                options.add_argument("--ignore-ssl-errors")
                options.add_argument("--allow-running-insecure-content")
                options.add_argument("--ignore-certificate-errors-spki-list")
                options.add_argument("--disable-background-networking")
                options.add_argument("--disable-sync")
                options.add_experimental_option("excludeSwitches", ["enable-logging"])
                options.add_argument(f"--remote-debugging-port={9222 + i}")
                fingerprint = generate_fingerprint()
                options.add_argument(f"user-agent={fingerprint['user_agent']}")
                user_data_dir = os.path.join(current_dir, f"profile_proxy_{i}_{int(time.time())}")
                options.add_argument(f"user-data-dir={user_data_dir}")

                driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
                driver.get("about:blank")
                hwnd = self.get_chrome_window_handle(driver)
                if hwnd:
                    self.instances[i] = {"driver": driver, "proxy": proxy, "user_data_dir": user_data_dir, "hwnd": hwnd, "port": 9222 + i}
                    log(f"Started instance {i} with proxy {proxy}")
                else:
                    log(f"Failed to get window handle for instance {i}, skipping...")
                    driver.quit()
                    continue
                if batch_open_urls:
                    for url in batch_open_urls:
                        driver.get(url)
                        log(f"Opened URL {url} in instance {i}")
                tasks.append(asyncio.sleep(1))
            await asyncio.gather(*tasks)
            self.arrange_windows()
        except Exception as e:
            handle_error(e, "Starting Chrome instances with proxy")

    def get_chrome_window_handle(self, driver):
        try:
            max_attempts = 5
            for attempt in range(max_attempts):
                hwnd = win32gui.FindWindow("Chrome_WidgetWin_1", None)
                if hwnd and win32gui.IsWindowVisible(hwnd):
                    return hwnd
                log(f"Attempt {attempt + 1}/{max_attempts} to get window handle failed, retrying...")
                time.sleep(2)
            log("Failed to get Chrome window handle after multiple attempts")
            return None
        except Exception as e:
            log(f"Error getting Chrome window handle: {e}")
            return None

    def arrange_windows(self, custom_layout=None):
        if not self.instances:
            log("No instances available to arrange")
            return

        screen_width, screen_height = pyautogui.size()
        num_instances = len(self.instances)

        if custom_layout:
            for i, instance in enumerate(self.instances.values()):
                if i < len(custom_layout) and instance["hwnd"]:
                    x, y, width, height = custom_layout[i]
                    win32gui.MoveWindow(instance["hwnd"], x, y, width, height, True)
                    log(f"Arranged instance {i} at custom position ({x}, {y}) with size ({width}, {height})")
        else:
            if num_instances == 5:
                cols = 5
                rows = 1
            else:
                cols = min(int((num_instances ** 0.5) + 0.5), 5)
                rows = (num_instances + cols - 1) // cols

            width = screen_width // cols
            height = screen_height // rows

            for i, instance in self.instances.items():
                if instance["hwnd"]:
                    x = (i % cols) * width
                    y = (i // cols) * height
                    win32gui.MoveWindow(instance["hwnd"], x, y, width, height, True)
                    log(f"Arranged instance {i} at grid position ({x}, {y}) with size ({width}, {height})")

    def batch_open_url(self, urls: list = None):
        if urls is None or not urls:
            root = tk.Tk()
            root.withdraw()
            urls_input = simpledialog.askstring("批量打开", "请输入 URL（用逗号或换行分隔多个 URL）：", parent=root)
            root.destroy()
            if not urls_input:
                return
            urls = [url.strip() for url in urls_input.replace(',', '\n').split('\n') if url.strip()]

        if not self.instances:
            log("No instances available to open URLs")
            messagebox.showwarning("警告", "请先启动实例")
            return

        for instance_id, instance_info in self.instances.items():
            try:
                for url in urls:
                    if not url.startswith(('http://', 'https://')):
                        url = 'https://' + url
                    instance_info["driver"].get(url)
                    log(f"Opened URL {url} in instance {instance_id} with proxy {instance_info['proxy'] or 'None'}")
                    time.sleep(0.5)
            except Exception as e:
                handle_error(e, f"Opening URL {url} in instance {instance_id}")

    def select_instances(self, instance_ids: list):
        self.selected_instances = [inst for i, inst in enumerate(self.instances) if i in instance_ids]
        log(f"Selected instances for synchronization: {instance_ids}")

    async def stop_instances(self, instance_ids: list = None):
        tasks = []
        try:
            instances_to_stop = self.instances if instance_ids is None else [inst for i, inst in enumerate(self.instances) if i in instance_ids]
            for instance_id, instance_info in instances_to_stop.items():
                try:
                    instance_info["driver"].get("about:blank")
                    time.sleep(1)
                    instance_info["driver"].quit()
                except Exception as e:
                    log(f"Error quitting instance {instance_info['hwnd']}: {e}")
                if os.path.exists(instance_info["user_data_dir"]):
                    import shutil
                    shutil.rmtree(instance_info["user_data_dir"], ignore_errors=True)
                log(f"Stopped Chrome instance with proxy {instance_info['proxy'] or 'None'}")
                tasks.append(asyncio.sleep(0.5))
            await asyncio.gather(*tasks)
            if instance_ids is None:
                self.instances.clear()
            else:
                self.instances = {i: inst for i, inst in enumerate(self.instances) if i not in instance_ids}
        except Exception as e:
            handle_error(e, "Stopping Chrome instances")

    def show_no_proxy_message(self):
        root = tk.Tk()
        root.withdraw()
        messagebox.showwarning("代理不可用", "没有可用的代理，程序将继续运行无代理模式。")
        root.destroy()

    def start_sync(self):
        if not self.instances:
            messagebox.showwarning("警告", "没有可用的实例")
            return
        
        if self.sync_active:
            messagebox.showwarning("警告", "同步已在运行")
            return
        
        valid_instances = []
        for instance_id, instance_info in self.instances.items():
            try:
                if instance_info["driver"].session_id:
                    instance_info["driver"].execute_script("window.focus();")
                    win32gui.SetForegroundWindow(instance_info["hwnd"])
                    valid_instances.append(instance_info)
                else:
                    log(f"Instance {instance_info['hwnd']} has invalid session, removing...")
            except Exception as e:
                log(f"Failed to validate instance {instance_info['hwnd']}: {e}")
        
        if not valid_instances:
            messagebox.showwarning("警告", "所有实例均无效，请重新启动实例")
            return

        self.sync_active = True
        self.selected_instances = valid_instances
        self.event_queue = queue.Queue()
        self.current_instance = self.selected_instances[0] if self.selected_instances else None  # 设置当前实例

        self.sync_thread = threading.Thread(target=self.sync_worker, daemon=True)
        self.sync_thread.start()

        try:
            self.mouse_listener = mouse.Listener(on_click=self.on_mouse_click_wrapper)
            self.keyboard_listener = keyboard.Listener(on_press=self.on_key_press_wrapper)
            
            self.mouse_listener.start()
            self.keyboard_listener.start()
            log("Started mouse and keyboard synchronization for selected instances")
            messagebox.showinfo("同步", "已开始同步所有实例")
        except Exception as e:
            log(f"Failed to start listeners: {e}")
            self.stop_sync()

    def stop_sync(self):
        if self.sync_active:
            self.sync_active = False
            if self.mouse_listener:
                self.mouse_listener.stop()
            if self.keyboard_listener:
                self.keyboard_listener.stop()
            if hasattr(self, 'sync_thread') and self.sync_thread.is_alive():
                self.sync_thread.join(timeout=2)
            messagebox.showinfo("同步", "已停止同步")
            log("Synchronization stopped")
        else:
            messagebox.showwarning("警告", "没有正在运行的同步")

    def sync_worker(self):
        while self.sync_active:
            try:
                event = self.event_queue.get(timeout=0.1)
                log(f"Processing event: {event}")  # 添加日志以查看事件
                if event["type"] == "mouse_click":
                    for instance_id, instance in self.instances.items():  # 遍历所有实例
                        self.on_mouse_click(event["x"], event["y"], event["button"], event["pressed"], instance)
                elif event["type"] == "key_press":
                    for instance_id, instance in self.instances.items():  # 遍历所有实例
                        self.on_key_press(event["key"], instance)
                self.event_queue.task_done()  # 确保任务完成
            except queue.Empty:
                continue
            except Exception as e:
                log(f"Sync worker error: {e}")
                continue

    def is_browser_active(self, browser_type="chrome"):
        """检查当前活动窗口是否为指定浏览器"""
        active_window = win32gui.GetForegroundWindow()
        if not active_window:
            return False
        class_name = win32gui.GetClassName(active_window)
        if browser_type == "chrome":
            return "Chrome_WidgetWin_1" in class_name
        elif browser_type == "firefox":
            return "MozillaWindowClass" in class_name  # Firefox 窗口类名
        return False

    def get_active_element_type(self, driver):
        """确定当前焦点元素是地址栏还是搜索框"""
        try:
            # 尝试找到地址栏（Chrome 导航栏）
            address_bar = driver.find_element(By.ID, "url")
            if address_bar.is_displayed() and address_bar.is_enabled():
                return "address_bar"

            # 尝试找到搜索框（如 Google 搜索框）
            search_box = driver.find_element(By.NAME, "q")
            if search_box.is_displayed() and search_box.is_enabled():
                return "search_box"

            # 默认返回 None，表示非输入区域
            return None
        except Exception:
            return None

    def on_mouse_click_wrapper(self, x, y, button, pressed):
        """鼠标点击事件的包装器，将事件放入队列"""
        if not self.sync_active or not self.is_browser_active():
            log("操作不在浏览器内，跳过点击同步")
            return
        log(f"Mouse click captured: x={x}, y={y}, button={button}, pressed={pressed}")
        self.event_queue.put({"type": "mouse_click", "x": x, "y": y, "button": button, "pressed": pressed})

    def on_key_press_wrapper(self, key):
        """键盘按下事件的包装器，传递当前实例"""
        if self.current_instance:
            self.on_key_press(key, self.current_instance)

    def on_mouse_click(self, x, y, button, pressed, instance):
        """处理鼠标点击事件并同步到所有实例"""
        if not self.sync_active or not self.is_browser_active():
            log("操作不在浏览器内，跳过点击同步")
            return

        driver = instance["driver"]
        try:
            # 获取当前活动窗口的边界
            active_window = win32gui.GetForegroundWindow()
            window_rect = win32gui.GetWindowRect(active_window)
            log(f"浏览器窗口边界: {window_rect}")  # 添加日志以查看窗口边界

            # 检查点击位置是否在窗口范围内
            if not (window_rect[0] <= x <= window_rect[2] and window_rect[1] <= y <= window_rect[3]):
                log(f"Skipping click sync: position ({x}, {y}) is outside window bounds")
                return

            driver.execute_script("window.focus();")
            element = driver.execute_script(f"return document.elementFromPoint({x}, {y});")
            if element is not None:
                element.click()  # 点击指定位置
                log(f"Synchronized click at ({x}, {y}) to instance {instance['hwnd']}")
            else:
                log(f"Failed to find element at ({x}, {y}) for instance {instance['hwnd']}")
        except Exception as e:
            log(f"Failed to sync click to instance {instance['hwnd']}: {e}")

    def on_mouse_scroll(self, x, y, dx, dy):
        if not self.sync_active or not self.is_browser_active():
            return
        
        active_window = win32gui.GetForegroundWindow()
        window_rect = win32gui.GetWindowRect(active_window)
        if not (window_rect[0] <= x <= window_rect[2] and window_rect[1] <= y <= window_rect[3]):
            log(f"Skipping scroll sync: mouse position ({x}, {y}) is outside Chrome window bounds {window_rect}")
            return
        
        for instance in self.selected_instances:
            driver = instance["driver"]
            try:
                # 聚焦当前实例并切换到活动标签页
                driver.execute_script("window.focus();")
                win32gui.SetForegroundWindow(instance["hwnd"])
                for handle in driver.window_handles:
                    driver.switch_to.window(handle)
                    driver.execute_script("window.focus();")

                scroll_amount = dy * 100
                driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
                log(f"Synchronized scroll to instance {instance['hwnd']} by {scroll_amount} pixels")
            except Exception as e:
                log(f"Failed to sync scroll to instance {instance['hwnd']}: {e}")

    def on_key_press(self, key, instance):
        """处理键盘按下事件并同步到所有实例"""
        if not self.sync_active:
            return

        for inst_id, inst in self.instances.items():  # 遍历所有实例
            driver = inst["driver"]
            try:
                # 获取按键字符或名称
                key_char = key.char if hasattr(key, 'char') else str(key).replace("Key.", "")
                log(f"Key pressed: {key_char}")  # 添加日志以查看按键

                # 发送键盘输入
                driver.execute_script("window.focus();")
                driver.execute_script(f"document.activeElement.value += '{key_char}';")  # 发送按键
                log(f"Synchronized key {key_char} to instance {inst['hwnd']}")
            except Exception as e:
                log(f"Failed to sync key {key_char} to instance {inst['hwnd']}: {e}")

    def on_key_release(self, key):
        """处理键盘释放事件"""
        if not self.sync_active:
            return

        if key in self.last_released_keys:
            return  # 如果按键已经处理过，则跳过

        self.last_released_keys.add(key)  # 记录已释放的按键
        print(f"Key released: {key}")  # 记录按键释放事件

    def reset_key_tracking(self):
        """重置已释放的按键跟踪"""
        self.last_released_keys.clear()  # 清空已释放的按键记录

    def show_gui(self):
        root = tk.Tk()
        root.title("Chrome Instance Manager - Auto Layout & Sync")

        def start_all():
            urls_input = url_entry.get("1.0", tk.END).strip()
            urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
            num = int(num_instances_entry.get() or 5)
            self.num_instances = min(num, 25)
            asyncio.run(self.start_instances(urls))

        def stop_all():
            asyncio.run(self.stop_instances())
            messagebox.showinfo("停止", "已停止所有 Chrome 实例")

        def stop_selected():
            selected = [i for i, var in enumerate(vars) if var.get()]
            if selected:
                asyncio.run(self.stop_instances(selected))
                messagebox.showinfo("停止", f"已停止选定实例 {selected}")
            else:
                messagebox.showwarning("警告", "请选择要停止的实例")

        def batch_open():
            urls_input = url_entry.get("1.0", tk.END).strip()
            urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
            if urls:
                self.batch_open_url(urls)
                messagebox.showinfo("批量打开", f"已为所有实例打开 URL: {', '.join(urls)}")
            else:
                messagebox.showwarning("警告", "请输入至少一个 URL")

        def arrange_windows_auto():
            self.arrange_windows()
            messagebox.showinfo("自动布局", f"已根据 {len(self.instances)} 个实例的动态网格布局排列窗口（5x1 优先）")

        def arrange_windows_custom():
            custom_layout = []
            screen_width, screen_height = pyautogui.size()
            for i in range(self.num_instances):
                x = simpledialog.askinteger("自定义布局", f"实例 {i} 的 X 坐标（0-{screen_width}）：", parent=root, minvalue=0, maxvalue=screen_width)
                y = simpledialog.askinteger("自定义布局", f"实例 {i} 的 Y 坐标（0-{screen_height}）：", parent=root, minvalue=0, maxvalue=screen_height)
                width = simpledialog.askinteger("自定义布局", f"实例 {i} 的宽度（100-{screen_width}）：", parent=root, minvalue=100, maxvalue=screen_width)
                height = simpledialog.askinteger("自定义布局", f"实例 {i} 的高度（100-{screen_height}）：", parent=root, minvalue=100, maxvalue=screen_height)
                if x is not None and y is not None and width is not None and height is not None:
                    custom_layout.append((x, y, width, height))
                else:
                    messagebox.showwarning("警告", f"实例 {i} 的布局输入不完整，取消自定义布局")
                    return
            self.arrange_windows(custom_layout)
            messagebox.showinfo("自定义布局", "已按自定义坐标排列窗口")

        ttk.Label(root, text="实例数量 (1-25):").grid(row=0, column=0, padx=5, pady=5)
        num_instances_entry = ttk.Entry(root)
        num_instances_entry.grid(row=0, column=1, padx=5, pady=5)
        num_instances_entry.insert(0, "5")

        ttk.Label(root, text="批量打开 URL（每行一个 URL）:").grid(row=1, column=0, padx=5, pady=5)
        url_entry = tk.Text(root, height=4, width=40)
        url_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Button(root, text="启动所有实例", command=start_all).grid(row=2, column=0, padx=5, pady=5)
        ttk.Button(root, text="停止所有实例", command=stop_all).grid(row=2, column=1, padx=5, pady=5)
        ttk.Button(root, text="停止选定实例", command=stop_selected).grid(row=2, column=2, padx=5, pady=5)
        ttk.Button(root, text="开始同步", command=self.start_sync).grid(row=3, column=0, padx=5, pady=5)
        ttk.Button(root, text="停止同步", command=self.stop_sync).grid(row=3, column=1, padx=5, pady=5)
        ttk.Button(root, text="批量打开网页", command=batch_open).grid(row=3, column=2, padx=5, pady=5)
        ttk.Button(root, text="自动 5x1 网格布局", command=arrange_windows_auto).grid(row=4, column=0, padx=5, pady=5)
        ttk.Button(root, text="自定义坐标布局", command=arrange_windows_custom).grid(row=4, column=1, padx=5, pady=5)

        vars = [tk.BooleanVar() for _ in range(25)]
        for i in range(25):
            ttk.Checkbutton(root, text=f"实例 {i}", variable=vars[i]).grid(row=5 + i, column=0, columnspan=3, padx=5, pady=2)

        root.mainloop()

if __name__ == "__main__":
    manager = ChromeManager()
    manager.show_gui()
