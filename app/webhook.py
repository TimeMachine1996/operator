import base64
import json
import logging
import os
from typing import Dict, List, Any, Optional

logger = logging.getLogger("webhook")

# 从环境变量获取Fluentd镜像
FLUENTD_IMAGE = os.environ.get("FLUENTD_IMAGE", "fluent/fluentd:v1.14")
# 从环境变量获取日志聚合器地址
AGGREGATOR_HOST = os.environ.get("AGGREGATOR_HOST", "fluentd-aggregator.logging.svc.cluster.local")
AGGREGATOR_PORT = os.environ.get("AGGREGATOR_PORT", "24224")

def process_admission_request(request: Dict[str, Any]) -> Dict[str, Any]:
    """处理Kubernetes admission请求"""
    # 获取请求UID，用于响应
    uid = request["request"]["uid"]
    
    # 检查是否是Pod创建请求
    if request["request"]["kind"]["kind"] != "Pod":
        logger.info(f"Skipping non-Pod resource: {request['request']['kind']['kind']}")
        return create_admission_response(uid, allowed=True)
    
    # 获取Pod对象
    pod = request["request"]["object"]
    
    # 检查是否需要注入Fluentd
    if not should_inject_fluentd(pod):
        logger.info(f"Skipping Pod {pod['metadata'].get('name', 'unknown')}: injection not enabled")
        return create_admission_response(uid, allowed=True)
    
    # 创建注入Fluentd的补丁
    patch = create_fluentd_patch(pod)
    
    # 编码补丁
    encoded_patch = base64.b64encode(json.dumps(patch).encode()).decode()
    
    logger.info(f"Injecting Fluentd sidecar into Pod {pod['metadata'].get('name', 'unknown')}")
    
    # 返回带有补丁的响应
    return create_admission_response(uid, allowed=True, patch=encoded_patch)

def should_inject_fluentd(pod: Dict[str, Any]) -> bool:
    """检查是否应该注入Fluentd"""
    annotations = pod.get("metadata", {}).get("annotations", {})
    
    # 检查是否有启用注入的注解
    return annotations.get("fluentd-injector/inject", "false").lower() == "true"

def create_fluentd_patch(pod: Dict[str, Any]) -> List[Dict[str, Any]]:
    """创建注入Fluentd的JSON补丁"""
    patch = []
    
    # 获取Pod注解
    annotations = pod.get("metadata", {}).get("annotations", {})
    
    # 获取日志目录，默认为/var/log
    log_dir = annotations.get("fluentd-injector/log-dir", "/var/log")
    
    # 获取日志标签前缀，默认为应用名称
    tag_prefix = annotations.get(
        "fluentd-injector/tag-prefix", 
        pod.get("metadata", {}).get("labels", {}).get("app", "application")
    )
    
    # 创建卷挂载补丁
    volume_name = "log-volume"
    
    # 检查是否已有卷定义
    if "volumes" not in pod.get("spec", {}):
        patch.append({
            "op": "add",
            "path": "/spec/volumes",
            "value": []
        })
    
    # 添加日志卷
    patch.append({
        "op": "add",
        "path": "/spec/volumes/-",
        "value": {
            "name": volume_name,
            "emptyDir": {}
        }
    })
    
    # 为每个容器添加卷挂载
    for i, container in enumerate(pod.get("spec", {}).get("containers", [])):
        # 检查容器是否已有卷挂载
        if "volumeMounts" not in container:
            patch.append({
                "op": "add",
                "path": f"/spec/containers/{i}/volumeMounts",
                "value": []
            })
        
        # 添加日志卷挂载
        patch.append({
            "op": "add",
            "path": f"/spec/containers/{i}/volumeMounts/-",
            "value": {
                "name": volume_name,
                "mountPath": log_dir
            }
        })
    
    # 添加Fluentd sidecar容器
    fluentd_container = {
        "name": "fluentd-sidecar",
        "image": FLUENTD_IMAGE,
        "resources": {
            "limits": {
                "memory": "200Mi"
            },
            "requests": {
                "cpu": "100m",
                "memory": "100Mi"
            }
        },
        "env": [
            {
                "name": "FLUENT_AGGREGATOR_HOST",
                "value": AGGREGATOR_HOST
            },
            {
                "name": "FLUENT_AGGREGATOR_PORT",
                "value": AGGREGATOR_PORT
            },
            {
                "name": "LOG_DIR",
                "value": log_dir
            },
            {
                "name": "TAG_PREFIX",
                "value": tag_prefix
            },
            {
                "name": "POD_NAME",
                "valueFrom": {
                    "fieldRef": {
                        "fieldPath": "metadata.name"
                    }
                }
            },
            {
                "name": "POD_NAMESPACE",
                "valueFrom": {
                    "fieldRef": {
                        "fieldPath": "metadata.namespace"
                    }
                }
            }
        ],
        "volumeMounts": [
            {
                "name": volume_name,
                "mountPath": log_dir
            }
        ]
    }
    
    # 添加Fluentd容器到Pod
    patch.append({
        "op": "add",
        "path": "/spec/containers/-",
        "value": fluentd_container
    })
    
    return patch

def create_admission_response(uid: str, allowed: bool, patch: Optional[str] = None) -> Dict[str, Any]:
    """创建admission响应"""
    response = {
        "apiVersion": "admission.k8s.io/v1",
        "kind": "AdmissionReview",
        "response": {
            "uid": uid,
            "allowed": allowed
        }
    }
    
    # 如果有补丁，添加到响应中
    if patch:
        response["response"]["patchType"] = "JSONPatch"
        response["response"]["patch"] = patch
    
    return response