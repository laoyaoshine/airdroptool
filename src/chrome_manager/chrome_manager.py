import asyncio
import subprocess
import os
from ..core.fingerprint import generate_fingerprint
from ..core.proxy_manager import ProxyManager
from ..core.tools import log, handle_error
import logging
import tkinter as tk
from tkinter import messagebox
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# 设置日志配置
logging.basicConfig(level=logging.INFO)

class ChromeManager:
    def __init__(self):
        self.proxy_manager = ProxyManager()  # 假设您有一个 ProxyManager 类
        self.driver = None

    async def start_instances(self):
        if not self.proxy_manager.proxies:
            logging.warning("No valid proxies available. Proceeding without using a proxy.")
            self.show_no_proxy_message()
            await self.start_chrome_instances_without_proxy()
            return

        # 如果有代理，继续使用代理
        for i in range(len(self.proxy_manager.proxies)):
            proxy = self.proxy_manager.proxies[i]
            await self.start_chrome_instance_with_proxy(proxy)

    async def start_chrome_instances_without_proxy(self):
        """启动 Chrome 实例的逻辑，不使用代理"""
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")  # 启动时最大化窗口
        options.add_argument("--no-sandbox")  # 可能有助于解决某些启动问题
        options.add_argument("--disable-dev-shm-usage")  # 解决资源限制问题
        options.add_argument("--disable-gpu")  # 禁用 GPU 加速
        options.add_argument("--disable-infobars")  # 禁用信息栏
        options.add_argument("--remote-debugging-port=9222")  # 启用远程调试
        options.add_argument("user-data-dir=C:\\path\\to\\new\\profile")  # 替换为新的配置文件路径

        service = Service(ChromeDriverManager().install())
        service.start()

        try:
            self.driver = webdriver.Chrome(service=service, options=options)
            logging.info("Chrome started without proxy.")
        except Exception as e:
            logging.error(f"Failed to start Chrome: {e}")
        finally:
            service.stop()

    async def start_chrome_instance_with_proxy(self, proxy):
        """启动 Chrome 实例的逻辑，使用代理"""
        options = webdriver.ChromeOptions()
        # 在这里添加代理设置
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        logging.info(f"Chrome started with proxy: {proxy}")

    def show_no_proxy_message(self):
        """弹出窗口提示代理不可用"""
        root = tk.Tk()
        root.withdraw()  # 隐藏主窗口
        messagebox.showwarning("代理不可用", "没有可用的代理，程序将继续运行。")
        root.destroy()

    async def stop_instances(self):
        """异步停止所有实例"""
        try:
            self.driver.quit()
        except Exception as e:
            handle_error(e, "Stopping Chrome instance")

if __name__ == "__main__":
    manager = ChromeManager()
    proxy_file = "proxies.csv"
    if not os.path.exists(proxy_file):
        log(f"Proxy file '{proxy_file}' not found. Please create it with proxy details (e.g., IP,Port).")
    else:
        asyncio.run(manager.proxy_manager.batch_import_proxies(proxy_file))
        asyncio.run(manager.start_instances())