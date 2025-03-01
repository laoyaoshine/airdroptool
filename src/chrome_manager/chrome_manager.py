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
import threading
from selenium.webdriver.common.keys import Keys
from pynput import mouse, keyboard
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
import queue
import requests

# 设置日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

current_dir = os.path.dirname(os.path.abspath(__file__))
icon_dir = os.path.join(current_dir, "..", "icon")

class ChromeManager:
    def __init__(self, num_instances: int = 5):
        self.num_instances = min(num_instances, 25)
        self.proxy_manager = ProxyManager()
        self.instances = []
        self.selected_instances = []
        self.sync_active = False
        self.main_instance = None  # 用于存储主浏览器实例
        self.check_system_resources()
        self.last_click_time = 0
        self.click_debounce_interval = 0.2
        self.last_click_event = None
        self.event_queue = queue.Queue()
        self.last_released_keys = set()
        self.last_key_time = 0
        self.key_debounce_interval = 0.1  # 100ms
        self.special_keys = {
            'space': Keys.SPACE,
            'enter': Keys.RETURN,
            'backspace': Keys.BACKSPACE,
            'tab': Keys.TAB,
            'esc': Keys.ESCAPE,
            'delete': Keys.DELETE,
            'shift': Keys.SHIFT,
            'ctrl': Keys.CONTROL,
            'alt': Keys.ALT,
            'cmd': Keys.COMMAND
        }
        self.main_browser_hwnd = None  # 用于标记主浏览器

    def check_system_resources(self):
        cpu_usage = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        if cpu_usage > 80 or memory.percent > 90:
            log("Warning: System resources low. Limiting instances.")
            self.num_instances = min(self.num_instances, 2)

    def validate_proxy(self, proxy: str) -> bool:
        try:
            proxies = {"http": f"http://{proxy}", "https": f"https://{proxy}"}
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
                options.add_argument("--disable-gpu")
                options.add_argument("--remote-debugging-port={}".format(9222 + i))
                user_data_dir = os.path.join(os.getcwd(), f"profile_no_proxy_{i}_{int(time.time())}")
                options.add_argument(f"user-data-dir={user_data_dir}")

                service = Service(ChromeDriverManager().install())
                service.start_timeout = 30
                
                try:
                    driver = webdriver.Chrome(service=service, options=options)
                    driver.get("about:blank")
                    hwnd = self.get_chrome_window_handle(driver)
                    if hwnd:
                        self.instances.append({"driver": driver, "hwnd": hwnd, "user_data_dir": user_data_dir, "proxy": None})
                        logger.info(f"Started Chrome instance {i} on hwnd {hwnd}")
                        
                        # 设置第一个实例为主浏览器
                        if i == 0:
                            self.main_instance = self.instances[-1]
                    else:
                        logger.error(f"Failed to get window handle for instance {i}, skipping...")
                        driver.quit()
                        continue
                    
                    if batch_open_urls:
                        for url in batch_open_urls:
                            driver.get(url)
                            logger.info(f"Opened URL {url} in instance {i}")
                    
                    tasks.append(asyncio.sleep(1))
                
                except Exception as e:
                    logger.error(f"Error starting Chrome instances: {e}")  # 处理异常
                
            await asyncio.gather(*tasks)
            self.arrange_windows()
        except Exception as e:
            logger.error(f"Error starting Chrome instances: {e}")  # 处理异常

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
                options.add_argument("--disable-infobars")
                options.add_argument("--ignore-ssl-errors")
                options.add_argument("--allow-running-insecure-content")
                options.add_argument("--ignore-certificate-errors-spki-list")
                options.add_experimental_option("excludeSwitches", ["enable-logging"])
                port = 9222 + i
                options.add_argument(f"--remote-debugging-port={port}")
                fingerprint = generate_fingerprint()
                options.add_argument(f"user-agent={fingerprint['user_agent']}")
                user_data_dir = os.path.join(current_dir, f"profile_proxy_{i}_{int(time.time())}")
                options.add_argument(f"user-data-dir={user_data_dir}")

                driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
                driver.get("about:blank")
                hwnd = self.get_chrome_window_handle(driver)
                if hwnd:
                    self.instances.append({"driver": driver, "proxy": proxy, "user_data_dir": user_data_dir, "hwnd": hwnd})
                    log(f"Started Chrome instance {i} with proxy {proxy}")
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
            hwnd = win32gui.FindWindow("Chrome_WidgetWin_1", None)
            return hwnd if hwnd else None
        except Exception as e:
            logger.error(f"Error getting Chrome window handle: {e}")
            return None

    def arrange_windows(self):
        """排列所有浏览器窗口"""
        if not self.instances:
            return

        screen_width = 1920  # 假设屏幕宽度
        screen_height = 1080  # 假设屏幕高度
        num_instances = len(self.instances)

        # 计算每个窗口的宽度和高度
        window_width = screen_width // num_instances
        window_height = screen_height // 2  # 假设每个窗口的高度为屏幕高度的一半

        for index, instance in enumerate(self.instances):
            hwnd = instance["hwnd"]
            if hwnd and win32gui.IsWindow(hwnd):
                x_position = index * window_width
                y_position = 0  # 可以根据需要调整
                win32gui.MoveWindow(hwnd, x_position, y_position, window_width, window_height, True)
                logger.info(f"Arranged window {hwnd} to position ({x_position}, {y_position})")

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

        for instance in self.instances:
            try:
                for url in urls:
                    if not url.startswith(('http://', 'https://')):
                        url = 'https://' + url
                    instance["driver"].get(url)
                    log(f"Opened URL {url} in instance with proxy {instance['proxy'] or 'None'}")
                    time.sleep(0.5)
            except Exception as e:
                handle_error(e, f"Opening URL {url} in instance")

    def select_instances(self, instance_ids: list):
        self.selected_instances = [inst for i, inst in enumerate(self.instances) if i in instance_ids]
        log(f"Selected instances for synchronization: {instance_ids}")

    async def stop_instances(self, instance_ids: list = None):
        tasks = []
        try:
            instances_to_stop = self.instances if instance_ids is None else [inst for i, inst in enumerate(self.instances) if i in instance_ids]
            for instance in instances_to_stop:
                try:
                    instance["driver"].get("about:blank")
                    time.sleep(1)
                    instance["driver"].quit()
                except Exception as e:
                    log(f"Error quitting instance {instance['hwnd']}: {e}")
                    if "Connection refused" in str(e):
                        logger.warning(f"Connection refused for instance {instance['hwnd']}, retrying...")
                if os.path.exists(instance["user_data_dir"]):
                    import shutil
                    shutil.rmtree(instance["user_data_dir"], ignore_errors=True)
                log(f"Stopped Chrome instance with proxy {instance.get('proxy', 'None')}")
                tasks.append(asyncio.sleep(0.5))
            await asyncio.gather(*tasks)
            if instance_ids is None:
                self.instances.clear()
            else:
                self.instances = [inst for i, inst in enumerate(self.instances) if i not in instance_ids]
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
        
        self.sync_active = True

        # 启动鼠标和键盘监听器
        self.mouse_listener = mouse.Listener(on_click=self.on_mouse_click)
        self.keyboard_listener = keyboard.Listener(on_press=self.on_key_press)
        
        self.mouse_listener.start()
        self.keyboard_listener.start()
        logger.info("Started mouse and keyboard synchronization for selected instances")
        
        # 使用一个新的线程来处理对话框
        threading.Thread(target=self.show_sync_message).start()

    def show_sync_message(self):
        # 使用一个新的线程来显示对话框
        threading.Thread(target=self._show_sync_message).start()

    def _show_sync_message(self):
        # 显示同步对话框
        messagebox.showinfo("同步", "已开始同步所有实例")

    def stop_sync(self):
        self.sync_active = False
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        logger.info("Stopped synchronization")
        # 显示可关闭的消息框，并在一定时间后自动关闭
        messagebox.showinfo("同步", "已停止同步所有实例")
        root = tk.Tk()
        root.withdraw()
        root.after(3000, root.destroy)  # 3秒后自动关闭
        root.mainloop()

    def on_mouse_click(self, x, y, button, pressed):
        if not self.main_instance:
            return
        
        driver = self.main_instance["driver"]
        hwnd = self.main_instance["hwnd"]
        
        if hwnd and win32gui.IsWindow(hwnd):  # 检查窗口句柄是否有效
            try:
                # 仅在主浏览器上设置前景窗口
                if win32gui.GetForegroundWindow() == hwnd:
                    # 获取浏览器窗口的大小和位置
                    rect = win32gui.GetWindowRect(hwnd)
                    window_x, window_y, window_width, window_height = rect
                    
                    # 确保点击坐标在窗口范围内
                    if window_x <= x <= window_x + window_width and window_y <= y <= window_y + window_height:
                        actions = ActionChains(driver)
                        actions.move_by_offset(x - window_x, y - window_y).click().perform()  # 计算相对坐标
                        actions.reset_actions()
                        logger.info(f"Synchronized click to main instance {hwnd} at ({x}, {y})")

                        # 同步到其他浏览器，跳过主浏览器
                        for instance in self.instances:
                            if instance["hwnd"] != hwnd:  # 只同步到其他浏览器
                                self.sync_click_to_instance(instance, x - window_x, y - window_y, button, pressed)
            except Exception as e:
                logger.error(f"Failed to sync click to instance {hwnd}: {e}")
        else:
            logger.error(f"Invalid window handle for main instance.")

    def sync_click_to_instance(self, instance, x, y, button, pressed):
        try:
            driver = instance["driver"]
            hwnd = instance["hwnd"]
            # 不设置前景窗口，只执行点击操作
            actions = ActionChains(driver)
            actions.move_by_offset(x, y).click().perform()
            actions.reset_actions()
            log(f"Synchronized click to instance {hwnd} at ({x}, {y})")
        except Exception as e:
            log(f"Failed to sync click to instance {hwnd}: {e}")

    def on_key_press(self, key):
        if not self.main_instance:
            return
        
        driver = self.main_instance["driver"]
        hwnd = self.main_instance["hwnd"]
        
        if hwnd and win32gui.IsWindow(hwnd):  # 检查窗口句柄是否有效
            try:
                # 仅在主浏览器上设置前景窗口
                if win32gui.GetForegroundWindow() == hwnd:
                    key_str = str(key)  # 将 KeyCode 转换为字符串
                    
                    # 跳过地址栏聚焦键（如 F6）
                    if key_str in ['Key.f6', 'Key.tab']:
                        return
                    
                    driver.switch_to.active_element.send_keys(key_str)  # 只在主浏览器中输入
                    logger.info(f"Synchronized key press {key_str} to main instance {hwnd}")

                    # 同步到其他浏览器
                    for instance in self.instances:
                        if instance["hwnd"] != hwnd:  # 只同步到其他浏览器
                            self.sync_key_to_instance(instance, key_str)  # 确保同步所有按键，包括回车
            except Exception as e:
                logger.error(f"Failed to send key {key} to main instance {hwnd}: {e}")
        else:
            logger.error(f"Invalid window handle for main instance.")

    def sync_key_to_instance(self, instance, key):
        try:
            driver = instance["driver"]
            hwnd = instance["hwnd"]
            # 不设置前景窗口，只执行键入操作
            driver.switch_to.active_element.send_keys(key)
            log(f"Synchronized key press {key} to instance {hwnd}")
        except Exception as e:
            log(f"Failed to sync key {key} to instance {hwnd}: {e}")

    def on_key_release(self, key):
        if not self.sync_active:
            return
        
        current_time = time.time()
        if current_time - self.last_key_time < self.key_debounce_interval:
            return
        
        key_char = key.char if hasattr(key, 'char') else str(key).replace("Key.", "")
        if not key_char or key_char == "None":
            return
        
        if key_char in self.last_released_keys:
            return
        
        self.last_key_time = current_time
        self.last_released_keys.add(key_char)
        active_window = win32gui.GetForegroundWindow()
        self.main_browser_hwnd = active_window  # 标记主浏览器
        self.event_queue.put({"type": "key_release", "key": key_char, "hwnd": active_window})
        log(f"Key released: {key_char} on main browser {active_window}")

    def sync_mouse_click(self, x, y, button, pressed, main_hwnd):
        for instance in self.selected_instances:
            try:
                driver = instance["driver"]
                hwnd = instance["hwnd"]
                if hwnd == main_hwnd:  # 跳过主浏览器
                    continue
                win32gui.SetForegroundWindow(hwnd)
                for handle in driver.window_handles:
                    driver.switch_to.window(handle)
                    actions = ActionChains(driver)
                    actions.move_by_offset(x, y).click().perform()
                    actions.reset_actions()
                log(f"Synchronized click to instance {hwnd} at ({x}, {y})")
            except Exception as e:
                log(f"Failed to sync click to instance {hwnd}: {e}")

    def sync_mouse_scroll(self, x, y, dx, dy, main_hwnd):
        for instance in self.selected_instances:
            try:
                driver = instance["driver"]
                hwnd = instance["hwnd"]
                if hwnd == main_hwnd:  # 跳过主浏览器
                    continue
                win32gui.SetForegroundWindow(hwnd)
                for handle in driver.window_handles:
                    driver.switch_to.window(handle)
                    driver.execute_script(f"window.scrollBy({dx * 100}, {dy * 100});")
                log(f"Synchronized scroll to instance {hwnd} by dx={dx*100}, dy={dy*100}")
            except Exception as e:
                log(f"Failed to sync scroll to instance {hwnd}: {e}")

    def sync_key(self, key, action, main_hwnd):
        for instance in self.selected_instances:
            try:
                driver = instance["driver"]
                hwnd = instance["hwnd"]
                if hwnd == main_hwnd:  # 跳过主浏览器
                    continue
                win32gui.SetForegroundWindow(hwnd)
                for handle in driver.window_handles:
                    driver.switch_to.window(handle)
                    element = driver.switch_to.active_element
                    if action == "press":
                        if key in self.special_keys:
                            element.send_keys(self.special_keys[key])
                        else:
                            element.send_keys(key)
                        log(f"Synchronized key press {key} to instance {hwnd}")
            except Exception as e:
                log(f"Failed to sync key {key} to instance {hwnd}: {e}")

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
