import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import asyncio
from ..core.proxy_manager import ProxyManager
from ..core.automation import run_multiple_airdrops
from ..core.sybil_defender import SybilDefender
from ..core.tools import log, handle_error

class AirdropGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Airdrop Tool")
        self.proxy_manager = ProxyManager()
        self.sybil_defender = SybilDefender("user@example.com")

        # 配置面板
        config_frame = ttk.LabelFrame(self.root, text="Configuration")
        config_frame.pack(pady=10)
        ttk.Button(config_frame, text="Import Proxies", command=self.import_proxies).pack()
        ttk.Button(config_frame, text="Start Airdrop", command=self.start_airdrop).pack()

        # 监控面板
        monitor_frame = ttk.LabelFrame(self.root, text="Monitor")
        monitor_frame.pack(pady=10)
        self.status_label = ttk.Label(monitor_frame, text="Status: Idle")
        self.status_label.pack()

        # 启动代理监控
        asyncio.create_task(self.proxy_manager.monitor_proxy(interval=5))

    def import_proxies(self):
        """批量导入代理"""
        file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if file_path:
            try:
                asyncio.run(self.proxy_manager.batch_import_proxies(file_path))
                messagebox.showinfo("Success", f"Imported {len(self.proxy_manager.proxies)} proxies")
                log(f"Imported {len(self.proxy_manager.proxies)} proxies from {file_path}")
            except Exception as e:
                handle_error(e, "Proxy import")

    def start_airdrop(self):
        """启动多开空投任务"""
        self.status_label.config(text="Status: Running")
        num_instances = simpledialog.askinteger("Input", "Number of instances (1-20):", minvalue=1, maxvalue=20, initialvalue=5)
        if num_instances:
            try:
                asyncio.run(run_multiple_airdrops("user@example.com", self.proxy_manager, self.sybil_defender, num_instances))
                messagebox.showinfo("Success", f"Completed {num_instances} airdrop tasks")
                log(f"Completed {num_instances} airdrop tasks")
            except Exception as e:
                handle_error(e, "Airdrop task")
            finally:
                self.status_label.config(text="Status: Idle")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = AirdropGUI()
    app.run()