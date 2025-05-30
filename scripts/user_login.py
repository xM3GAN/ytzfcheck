import os
import re
import sys
import time
from pprint import pprint
from urllib.parse import urljoin
from .zfn_api import Client
from .pre_auth import perform_pre_auth

# 从环境变量中提取教务系统的URL、用户名、密码和TOKEN等信息
force_push_message = os.environ.get("FORCE_PUSH_MESSAGE")
github_actions = os.environ.get("GITHUB_ACTIONS")
github_ref_name = os.environ.get("GITHUB_REF_NAME")
github_event_name = os.environ.get("GITHUB_EVENT_NAME")
github_actor = os.environ.get("GITHUB_ACTOR")
github_actor_id = os.environ.get("GITHUB_ACTOR_ID")
github_triggering_actor = os.environ.get("GITHUB_TRIGGERING_ACTOR")
repository_name = os.environ.get("REPOSITORY_NAME")
github_sha = os.environ.get("GITHUB_SHA")
github_workflow = os.environ.get("GITHUB_WORKFLOW")
github_run_number = os.environ.get("GITHUB_RUN_NUMBER")
github_run_id = os.environ.get("GITHUB_RUN_ID")
beijing_time = os.environ.get("BEIJING_TIME")
github_step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
# 新增前置认证相关环境变量
pre_auth_url = os.environ.get("PRE_AUTH_URL")
pre_auth_username = os.environ.get("PRE_AUTH_USERNAME")
pre_auth_password = os.environ.get("PRE_AUTH_PASSWORD")

# 工作流信息
workflow_info = (
    f"------\n"
    f"工作流信息：\n"
    f"Force Push Message：{force_push_message}\n"
    f"Branch Name：{github_ref_name}\n"
    f"Triggered By：{github_event_name}\n"
    f"Initial Run By：{github_actor}\n"
    f"Initial Run By ID：{github_actor_id}\n"
    f"Initiated Run By：{github_triggering_actor}\n"
    f"Repository Name：{repository_name}\n"
    f"Commit SHA：{github_sha}\n"
    f"Workflow Name：{github_workflow}\n"
    f"Workflow Number：{github_run_number}\n"
    f"Workflow ID：{github_run_id}\n"
    f"Beijing Time：{beijing_time}"
)

copyright_text = "Copyright © 2024 Klauthmos. All rights reserved."


def write_github_summary(run_log, lgn_code):
    # 检查 run_log 是否为空，若为空则赋值为"未知错误"
    if not run_log:
        run_log = "未知错误"

    # 检查 lgn_code 是否为空，若为空则赋值为"未知代码"
    if not lgn_code:
        lgn_code = "未知代码"

    summary_log = (
        f"# 正方教务管理系统成绩推送\n"
        f"你因 **{run_log}** 原因而登录失败，错误代码为 **{lgn_code}**。\n"
        f"若你不明白或不理解为什么登录失败，请到上游仓库的 "
        f"[Issue](https://github.com/NianBroken/ZFCheckScores/issues/new 'Issue') 中寻求帮助。\n"
        f"{workflow_info}\n"
        f"{copyright_text}"
    )

    # 将任意个数的换行替换为两个换行
    summary_log = re.sub("\n+", "\n\n", summary_log)

    # 将登录需要验证码写入到 GitHub Actions 的环境文件中
    with open(github_step_summary, "w", encoding="utf-8") as file:
        file.write(summary_log)


def login(url, username, password):
    # 检查是否需要前置认证
    if pre_auth_url and pre_auth_username and pre_auth_password:
        print("检测到前置认证配置，执行前置认证...")
        # 执行前置认证
        pre_auth_result = perform_pre_auth(
            pre_auth_url, 
            pre_auth_username, 
            pre_auth_password
        )
        
        if pre_auth_result["code"] != 1000:
            run_log = pre_auth_result["msg"]
            
            # 如果是Github Actions运行,则将运行日志写入到GitHub Actions的日志文件中
            if github_actions:
                write_github_summary(run_log, pre_auth_result["code"])
            
            sys.exit(f"你因{run_log}原因而登录失败，错误代码为{pre_auth_result['code']}。")
        
        # 前置认证成功，使用前置认证的会话继续登录教务系统
        session = pre_auth_result["session"]
        cookies = pre_auth_result["cookies"]
        print("前置认证成功，继续进行教务系统登录...")
    else:
        print("未检测到前置认证配置，直接登录教务系统...")
        # 无需前置认证，正常执行
        cookies = {}
        session = None
    
    base_url = url
    raspisanie = []
    ignore_type = []
    detail_category_type = []
    timeout = 10

    student_client = Client(
        cookies=cookies,
        base_url=base_url,
        raspisanie=raspisanie,
        ignore_type=ignore_type,
        detail_category_type=detail_category_type,
        timeout=timeout,
        session=session,  # 添加session参数
    )

    # 如果已经通过前置认证并有session，则直接使用该session
    # 否则执行普通的登录过程
    if session:
        # 已有前置认证会话，尝试直接访问教务系统
        print("尝试使用前置认证会话访问教务系统...")
        student_client.cookies = cookies
        student_client.sess = session
        # 检查是否可以直接访问教务系统
        try:
            # 简单测试访问，看是否已登录
            test_url = urljoin(base_url, "xtgl/index_initMenu.html")
            print(f"GET 测试访问教务系统: {test_url}")
            test_resp = session.get(test_url, timeout=20) # 增加超时时间
            print(f"GET 测试访问教务系统完成, 状态码: {test_resp.status_code}")
            
            if test_resp.status_code == 200 and "用户登录" not in test_resp.text:
                print("成功直接访问教务系统")
                # 成功直接访问教务系统
                return student_client
            print("无法直接访问教务系统，可能需要再次登录")
            # 如果无法直接访问，可能需要再次登录教务系统
        except Exception as e:
            print(f"测试访问教务系统出错: {str(e)}")
            # 访问出错，fallback到普通登录
            pass
    
    # 普通登录逻辑
    print("执行普通登录逻辑...")
    attempts = 5  # 最大重试次数
    while attempts > 0:
        if cookies == {}:
            print(f"第 {6 - attempts} 次尝试登录...")
            lgn = student_client.login(username, password)
            print(f"登录尝试结果: {lgn}")
            if lgn["code"] == 1001:
                run_log = "登录需要验证码"

                # 如果是Github Actions运行,则将运行日志写入到GitHub Actions的日志文件中
                if github_actions:
                    write_github_summary(run_log, lgn["code"])

                sys.exit(f"你因{run_log}原因而登录失败，错误代码为{lgn['code']}。")
                """
                verify_data = lgn["data"]
                with open(os.path.abspath("kaptcha.png"), "wb") as pic:
                    pic.write(base64.b64decode(verify_data.pop("kaptcha_pic")))
                verify_data["kaptcha"] = input("输入验证码：")
                ret = student_client.login_with_kaptcha(**verify_data)
                if ret["code"] != 1000:
                    pprint(ret)
                    sys.exit()
                pprint(ret)
                """
            elif lgn["code"] != 1000:
                if attempts == 1:
                    pprint(lgn)
                    run_log = lgn["msg"]

                    # 如果是Github Actions运行,则将运行日志写入到GitHub Actions的日志文件中
                    if github_actions:
                        write_github_summary(run_log, lgn["code"])

                # 如果未成功登录，等待1秒后重试
                time.sleep(1)
                attempts -= 1  # 剩余重试次数减1
                continue

            # 如果登录成功，则跳出重试循环
            break

    if attempts == 0:
        sys.exit(0)

    return student_client
