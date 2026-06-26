import configparser
import json
import os
import re
import shutil
import subprocess
import sys
import time

import undetected_chromedriver as uc
from notice import Notice
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def get_chrome_info():
    candidates = [
        "google-chrome",
        "google-chrome-stable",
        "chromium-browser",
        "chromium",
    ]

    for binary in candidates:
        binary_path = shutil.which(binary)
        if not binary_path:
            continue

        try:
            output = subprocess.check_output(
                [binary_path, "--version"], stderr=subprocess.STDOUT, text=True
            ).strip()
            match = re.search(r"(\d+)\.", output)
            if match:
                return binary_path, int(match.group(1))
        except Exception:
            continue

    return None, None


def build_chrome_options():
    options = uc.ChromeOptions()
    options.add_argument("--lang=zh-CN")
    options.add_experimental_option("prefs", {"intl.accept_languages": "zh-CN,zh"})
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
    )
    return options


def dismiss_dialogs(browser):
    """关闭所有可能的弹窗和遮挡层"""
    try:
        close_btn = browser.find_element(
            By.CSS_SELECTOR,
            '.arco-modal-close-btn, .arco-modal-close, [class*="close"]',
        )
        browser.execute_script("arguments[0].click();", close_btn)
        time.sleep(0.5)
    except Exception:
        pass

    browser.execute_script("""
        document.querySelectorAll(
            '.arco-modal-wrapper, .arco-modal-mask, .arco-modal, .arco-modal-container'
        ).forEach(m => m.remove());
        document.body.style.overflow = '';
    """)


def get_ak_coins(browser):
    """获取当前AK币数量"""
    try:
        element = browser.find_element(By.CSS_SELECTOR, '.coin-balance-value')
        text = element.text.strip()
        return int(re.search(r'(\d+)', text).group(1))
    except Exception:
        return -1


def run_single_account(email, password, push_key=""):
    """对单个账号执行登录和签到，返回结果消息"""
    result_msg = ""
    browser = None

    try:
        options = build_chrome_options()
        chrome_path, chrome_major = get_chrome_info()
        if chrome_path:
            options.binary_location = chrome_path
        if chrome_major:
            browser = uc.Chrome(options=options, version_main=chrome_major)
        else:
            browser = uc.Chrome(options=options)

        # ── 登录 ──
        browser.get("https://akile.ai/login")
        browser.maximize_window()
        time.sleep(2)
        dismiss_dialogs(browser)

        try:
            email_input = WebDriverWait(browser, 10).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, 'input[placeholder*="邮箱"]')
                )
            )
            email_input.send_keys(email)
            password_input = WebDriverWait(browser, 10).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, 'input[placeholder*="密码"]')
                )
            )
            password_input.send_keys(password)
        except TimeoutException as e:
            browser.save_screenshot(f"login_error_{email.replace('@','_')}.png")
            msg = f"[{email}] 邮箱或密码输入框没有加载出来: {e}"
            print(msg)
            Notice.serverJ(push_key, "Akile签到", msg)
            return msg

        try:
            submit_button = WebDriverWait(browser, 10).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, 'form button[type="submit"], form .arco-btn-primary')
                )
            )
            submit_button.click()
        except TimeoutException as e:
            msg = f"[{email}] 登录按钮没有加载出来: {e}"
            print(msg)
            Notice.serverJ(push_key, "Akile签到", msg)
            return msg

        time.sleep(3)

        # ── 签到 ──
        browser.get("https://akile.ai/console/ak-coin-shop")
        time.sleep(5)
        dismiss_dialogs(browser)

        prev_points = get_ak_coins(browser)
        print(f"[{email}] 当前AK币: {prev_points}")

        try:
            checkin_button = WebDriverWait(browser, 15).until(
                EC.element_to_be_clickable(
                    (By.XPATH, '//button[contains(., "每日签到")]')
                )
            )
            print(f"[{email}] 找到签到按钮，正在点击...")
            browser.execute_script("arguments[0].click();", checkin_button)
            time.sleep(3)

            cur_points = get_ak_coins(browser)
            if prev_points == -1:
                result_msg = f"[{email}] 签到成功, 当前有{cur_points}个AK币"
            else:
                gain = cur_points - prev_points if cur_points > 0 else 0
                result_msg = f"[{email}] 签到成功, 获得{gain}个AK币, 当前有{cur_points}个AK币"

        except TimeoutException:
            print(f"[{email}] 未找到签到按钮，检查是否已签到...")
            try:
                browser.find_element(By.XPATH, '//button[contains(., "已签到")]')
                result_msg = f"[{email}] 今日已签到, 现在有{prev_points}AK币"
            except Exception as e:
                browser.save_screenshot(f"debug_{email.replace('@','_')}.png")
                result_msg = f"[{email}] 签到按钮和已签到按钮都无法加载出来: {e}"
                print(result_msg)
                Notice.serverJ(push_key, "Akile签到", result_msg)
                return result_msg

        print(result_msg)
        Notice.serverJ(push_key, "Akile签到", result_msg)
        return result_msg

    except Exception as e:
        result_msg = f"[{email}] 签到异常: {e}"
        print(result_msg)
        Notice.serverJ(push_key, "Akile签到", result_msg)
        return result_msg
    finally:
        if browser:
            try:
                browser.quit()
            except Exception:
                pass


def load_accounts():
    """加载账号列表。优先级：AKILE_ACCOUNTS JSON > AKILE_EMAIL/PASSWORD 单账号 > config.ini"""
    # 方式1: AKILE_ACCOUNTS JSON 环境变量（多账号）
    accounts_json = os.getenv("AKILE_ACCOUNTS", "").strip()
    if accounts_json:
        try:
            accounts = json.loads(accounts_json)
            if isinstance(accounts, list) and len(accounts) > 0:
                return accounts
        except json.JSONDecodeError as e:
            print(f"AKILE_ACCOUNTS JSON 解析失败: {e}，回退到单账号模式")

    # 方式2: 单账号环境变量
    email = os.getenv("AKILE_EMAIL", "").strip()
    password = os.getenv("AKILE_PASSWORD", "").strip()
    push_key = os.getenv("AKILE_PUSH_KEY", "").strip()

    if email and password:
        return [{"email": email, "password": password, "push_key": push_key}]

    # 方式3: config.ini 配置文件
    try:
        config = configparser.ConfigParser()
        config.read("config.ini", encoding="utf-8")
        email = config.get("akile", "email")
        password = config.get("akile", "password")
        push_key = config.get("akile", "push_key", fallback="")
        return [{"email": email, "password": password, "push_key": push_key}]
    except Exception as e:
        print(f"读取 config.ini 失败: {e}")
        print("请在环境变量 AKILE_ACCOUNTS 或 AKILE_EMAIL/AKILE_PASSWORD 中配置账号")
        sys.exit(1)


if __name__ == "__main__":
    accounts = load_accounts()
    print(f"共加载 {len(accounts)} 个账号，开始签到...")

    results = []
    for i, acct in enumerate(accounts):
        email = acct.get("email", "")
        password = acct.get("password", "")
        push_key = acct.get("push_key", os.getenv("AKILE_PUSH_KEY", "").strip())

        if not email or not password:
            print(f"账号 {i+1} 缺少 email 或 password，跳过")
            continue

        print(f"\n{'='*50}")
        print(f"▶ 账号 {i+1}/{len(accounts)}: {email}")
        print(f"{'='*50}")
        result = run_single_account(email, password, push_key)
        results.append(result)

    print(f"\n{'='*50}")
    print("全部签到完成！")
    for r in results:
        print(f"  {r}")
