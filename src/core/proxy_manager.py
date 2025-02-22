import asyncio
import aiohttp
import csv
import time
import os
from typing import List, Dict
from .tools import log, handle_error

class ProxyManager:
    def __init__(self):
        self.proxies: List[str] = []
        self.active_proxies: Dict[str, Dict] = {}

    async def batch_import_proxies(self, file_path: str):
        """异步批量导入代理配置"""
        try:
            if not os.path.exists(file_path):
                log(f"Proxy file '{file_path}' not found. Please create it with proxy details (e.g., IP,Port).")
                return  # 或抛出异常：raise FileNotFoundError(f"Proxy file '{file_path}' not found")

            async with aiohttp.ClientSession() as session:
                with open(file_path, 'r') as file:
                    reader = csv.reader(file)
                    tasks = []
                    for row in reader:
                        proxy = f"http://{row[0]}:{row[1]}" if len(row) > 1 else row[0]
                        tasks.append(self.validate_proxy(session, proxy))
                    results = await asyncio.gather(*tasks)
                    self.proxies = [r["proxy"] for r in results if r["status"] == "valid"]
                    self.active_proxies = {r["proxy"]: r for r in results if r["status"] == "valid"}
                    log(f"Imported {len(self.proxies)} valid proxies from {file_path}")
        except Exception as e:
            handle_error(e, "Batch importing proxies")

    async def validate_proxy(self, session: aiohttp.ClientSession, proxy: str) -> Dict:
        """异步验证代理有效性"""
        try:
            async with session.get("https://www.google.com", proxy=proxy, timeout=aiohttp.ClientTimeout(total=5)) as response:
                latency = response.real_url.host if response.status == 200 else None
                return {"proxy": proxy, "status": "valid", "latency": latency}
        except Exception:
            return {"proxy": proxy, "status": "invalid", "latency": None}

    async def switch_proxy(self, driver, proxy: str):
        """异步快速切换代理"""
        from selenium import webdriver
        try:
            driver.quit()
            options = driver.options
            options.add_argument(f"--proxy-server={proxy}")
            return webdriver.Chrome(options=options)
        except Exception as e:
            handle_error(e, "Switching proxy")

    async def monitor_proxy(self, interval: float = 5):
        """异步实时监控代理状态"""
        while True:
            try:
                tasks = [self.validate_proxy(aiohttp.ClientSession(), proxy) for proxy in self.proxies]
                results = await asyncio.gather(*tasks)
                for result in results:
                    if result["status"] == "invalid":
                        if result["proxy"] in self.proxies:
                            self.proxies.remove(result["proxy"])
                            self.active_proxies.pop(result["proxy"], None)
                            log(f"Proxy {result['proxy']} failed, removed.")
                await asyncio.sleep(interval)
            except Exception as e:
                handle_error(e, "Monitoring proxies")