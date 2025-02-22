import hashlib
import time
import random
from datetime import datetime
from typing import Optional, List
from .tools import log, handle_error

class SybilDefender:
    def __init__(self, user_id: str, max_instances: int = 5, cooldown: float = 300.0):
        self.user_id = user_id
        self.max_instances = max_instances
        self.cooldown = cooldown  # 冷却时间（秒）
        self.instance_count = 0
        self.last_operation = datetime.now()
        self.operation_history: List[Dict] = []  # 记录操作历史

    def check_sybil(self) -> bool:
        """检查是否触发 Sybil 检测，添加更灵活的规则"""
        try:
            current_time = datetime.now()
            time_since_last = (current_time - self.last_operation).total_seconds()

            # 检查冷却时间和操作频率
            if time_since_last < random.uniform(1.0, self.cooldown / 10):
                time.sleep(random.uniform(1.0, 5.0))  # 随机延迟模拟人类行为

            # 检查实例数量
            if self.instance_count >= self.max_instances:
                raise Exception(f"Instance limit ({self.max_instances}) exceeded, potential Sybil attack detected.")

            # 记录操作历史
            self.operation_history.append({"time": current_time, "instance_id": f"inst_{random.randint(1, 1000)}"})
            if len(self.operation_history) > 100:  # 限制历史长度
                self.operation_history.pop(0)

            self.last_operation = current_time
            self.instance_count += 1
            log(f"Sybil check passed for user {self.user_id}")
            return True
        except Exception as e:
            handle_error(e, "Sybil check")

    def generate_unique_id(self) -> str:
        """生成唯一标识符，增加盐值以提高安全性"""
        try:
            salt = f"{self.user_id}_{time.time()}_{random.randint(1, 1000)}"
            return hashlib.sha256(salt.encode()).hexdigest()
        except Exception as e:
            handle_error(e, "Generating unique ID")

    def reset_instance_count(self):
        """手动重置实例计数（用于测试或错误恢复）"""
        try:
            self.instance_count = 0
            log("Instance count reset")
        except Exception as e:
            handle_error(e, "Resetting instance count")