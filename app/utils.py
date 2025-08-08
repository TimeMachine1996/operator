import os
import logging
from typing import Dict, Any

logger = logging.getLogger("webhook")

def get_env_or_default(key: str, default: str) -> str:
    """从环境变量获取值，如果不存在则使用默认值"""
    return os.environ.get(key, default)

def log_admission_request(request: Dict[str, Any]) -> None:
    """记录admission请求的详细信息"""
    try:
        kind = request["request"]["kind"]["kind"]
        namespace = request["request"]["namespace"]
        name = request["request"]["object"]["metadata"].get("name", "unknown")
        operation = request["request"]["operation"]
        
        logger.info(f"Processing {operation} request for {kind}/{name} in namespace {namespace}")
    except KeyError as e:
        logger.warning(f"Could not log request details: {e}")