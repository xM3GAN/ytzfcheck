import requests
import re
import sys
import os
import traceback
from pyquery import PyQuery as pq
from urllib.parse import urljoin

def perform_pre_auth(pre_auth_url, username, password):
    """
    执行前置认证
    
    Args:
        pre_auth_url: 前置认证URL
        username: 用户名
        password: 密码
        
    Returns:
        dict: 包含认证结果的字典
    """
    try:
        session = requests.Session()
        session.keep_alive = False
        
        headers = requests.utils.default_headers()
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
        headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3"
        
        # 访问前置认证页面获取CSRF token和执行信息
        req_login_page = session.get(pre_auth_url, headers=headers, timeout=10)
        if req_login_page.status_code != 200:
            return {"code": 2333, "msg": "前置认证系统无法访问"}
        
        # 使用PyQuery解析页面
        doc = pq(req_login_page.text)
        
        # 获取必要的表单数据
        execution_value = doc("input[name='execution']").attr("value")
        event_id = doc("input[name='_eventId']").attr("value")
        
        # 这里Password不需要加密，因为前置认证系统通常在前端处理加密
        login_data = {
            "username": username,
            "password": password,
            "_eventId": event_id,
            "cllt": "userNameLogin",
            "dllt": "generalLogin",
            "lt": "",
            "execution": execution_value
        }
        
        # 发送登录请求
        login_response = session.post(
            pre_auth_url,
            headers=headers,
            data=login_data,
            timeout=10,
            allow_redirects=False  # 不自动跟随重定向，因为我们需要手动处理
        )
        
        # 检查是否是重定向响应（成功登录应该是302重定向）
        if login_response.status_code == 302:
            redirect_url = login_response.headers.get("Location")
            if redirect_url:
                # 跟随重定向，获取webvpn的认证票据
                webvpn_response = session.get(
                    redirect_url, 
                    headers=headers,
                    timeout=10,
                    allow_redirects=True  # 现在允许自动跟随所有后续重定向
                )
                
                # 返回会话对象和cookies以便后续使用
                return {
                    "code": 1000,
                    "msg": "前置认证成功",
                    "session": session,
                    "cookies": session.cookies.get_dict()
                }
            else:
                return {"code": 2000, "msg": "前置认证成功但未获取到重定向URL"}
        
        # 检查是否登录失败
        elif login_response.status_code == 200:
            doc = pq(login_response.text)
            error_msg = doc("#msg").text()
            if error_msg:
                return {"code": 1002, "msg": f"前置认证失败：{error_msg}"}
            return {"code": 1001, "msg": "前置认证失败：未知原因"}
        
        return {"code": login_response.status_code, "msg": f"前置认证返回未知状态码：{login_response.status_code}"}
    
    except requests.exceptions.Timeout:
        return {"code": 1003, "msg": "前置认证超时"}
    except requests.exceptions.RequestException as e:
        traceback.print_exc()
        return {"code": 2333, "msg": f"前置认证请求异常：{str(e)}"}
    except Exception as e:
        traceback.print_exc()
        return {"code": 999, "msg": f"前置认证未记录的错误：{str(e)}"} 