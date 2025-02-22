import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def log(message: str):
    """记录日志"""
    logger.info(message)

def handle_error(exc: Exception, context: str = "Operation"):
    """处理错误并记录日志"""
    log(f"Error in {context}: {str(exc)}")
    raise exc