import random
from faker import Faker
import platform
from selenium.webdriver.chrome.options import Options
from .tools import log, handle_error

fake = Faker()

def generate_fingerprint():
    """生成独特的浏览器指纹，支持更多参数"""
    os_name = platform.system().lower()
    user_agent = fake.user_agent()
    canvas_data = f"canvas_{random.randint(1, 10000)}_{os_name}"
    webgl_data = f"webgl_{random.randint(1, 10000)}_{os_name}"
    return {
        "user_agent": user_agent,
        "canvas": canvas_data,
        "webgl": webgl_data,
        "lang": fake.language_code(),
        "resolution": f"{random.randint(800, 1920)}x{random.randint(600, 1080)}",
        "timezone": fake.timezone(),
        "platform": os_name
    }

def apply_fingerprint(driver, fingerprint):
    """将指纹应用到 Selenium 驱动，增强伪装"""
    try:
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": fingerprint["user_agent"]})
        driver.execute_script(f"""
            Object.defineProperty(navigator, 'language', {{value: '{fingerprint['lang']}'}});
            Object.defineProperty(navigator, 'platform', {{value: '{fingerprint['platform']}'}});
            Object.defineProperty(HTMLCanvasElement.prototype, 'toDataURL', {{value: () => '{fingerprint['canvas']}'}});
            Object.defineProperty(navigator, 'userAgent', {{value: '{fingerprint['user_agent']}'}});
        """)
        # 模拟 WebGL 指纹
        driver.execute_script(f"Object.defineProperty(WebGLRenderingContext.prototype, 'getParameter', {{value: () => '{fingerprint['webgl']}'}});")
        log(f"Applied fingerprint for driver: {fingerprint['user_agent']}")
    except Exception as e:
        handle_error(e, "Applying fingerprint")