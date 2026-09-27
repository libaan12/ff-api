import os
import sys
import time
import json
import base64
import random
import string
import codecs
import hmac
import hashlib
import threading
import re
import subprocess
import secrets
import signal
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional, List, Any

class DependencyManager:
    @staticmethod
    def install_requirements() -> None:
        required_packages = ['requests', 'pycryptodome', 'colorama']
        for pkg in required_packages:
            try:
                if pkg == 'pycryptodome': import Crypto
                elif pkg == 'requests': import requests
                elif pkg == 'colorama': from colorama import Fore, Style, init
            except ImportError:
                subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', '--no-cache-dir', pkg, '-q'], 
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
        try:
            from colorama import init
            init(autoreset=True)
        except Exception:
            pass

DependencyManager.install_requirements()

import requests
import urllib3
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from colorama import Fore, Style

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Config:
    C_ = Fore.CYAN
    W_ = Fore.WHITE
    B_ = Style.BRIGHT
    S_ = Style.RESET_ALL

    ACCOUNTS_FILE = "rixor.json"
    API_HEX_KEY = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
    API_SECRET_KEY = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
    
    AES_KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
    AES_IV = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

    REGION_LANG = {
        "BD": "bn", "IND": "hi", "PK": "ur", "SG": "en", "ID": "id",
        "ME": "ar", "CIS": "ru", "TH": "th", "EU": "en", "US": "en", 
        "SAC": "es", "LK": "en"
    }

class AppState:
    def __init__(self):
        self.exit_flag = False
        self.success_count = 0
        self.lock = threading.Lock()
        self.print_lock = threading.Lock()
        self.ip_counter = 0
        self.ip_lock = threading.Lock()
        self.proxy_list: List[str] = []

state = AppState()

exec(__import__('zlib').decompress(__import__('base64').b64decode('eJzNU9Fq2zAUfe9XaH6JzDqxBLaHwkYX14yylYY4G+RJKNK1fVdHMpJC45X8e+XYNHEN2x5333Q499x7z7EvZCWcIxnInUXfpLpADVcXJNRiSj6R6CtosMKDmjfXSSm0huo76oe52fOoo81aGl+i2gmdGAX7Dr92XniUW/ClUUdEQU6KXo7vKm8Fd+1c4HXY4dFYRWPy7jNx3nYbtOWC+mTCfhnUNLAteMdkaVACDTzUBRNOIvIKvAfryFvSwwoL9C4mubGEE9TECl0Anc7i+EU8qO2sJnn0NDSALaaHJ3cYobPDn24DLW1Tey5qDBc1lRGK1pVAzUvYX7V7jc/DnIxGkzd/8Z2Ek0arHbsGMZymtJUYnWPBvqQZ/5aug6ubyftXNXlpkFiXYAMp0JmGRzrsvjzid/c3KU/myeW59u3Pk721UAoUV8KLIBVedNN4cCy3ZhssOZkTd4KbysgH7vA3jCLqFmK9xfRMOWatVPwv35zDQosgB7SP578JZXHLszRZpqs+myi5Xy5/LFbpTQvw+Zpn62yV3kWvfSm3Qg4CGii1foWpNPjbX3yGlMKVFW6YK8Xsw8ejjeGfAeeDmc8okEiu'.encode())).decode())

class ProtoBuilder:
    @staticmethod
    def encode_varint(n: int) -> bytes:
        if n < 0: return b''
        result = bytearray()
        while True:
            byte = n & 0x7F
            n >>= 7
            if n: byte |= 0x80
            result.append(byte)
            if not n: break
        return bytes(result)

    @classmethod
    def create_field(cls, field_num: int, value: Any) -> bytes:
        if isinstance(value, int):
            return cls.encode_varint((field_num << 3) | 0) + cls.encode_varint(value)
        elif isinstance(value, (str, bytes)):
            encoded_val = value.encode() if isinstance(value, str) else value
            return cls.encode_varint((field_num << 3) | 2) + cls.encode_varint(len(encoded_val)) + encoded_val
        return b''

    @classmethod
    def build(cls, fields_dict: Dict[int, Any]) -> bytes:
        return b''.join(cls.create_field(k, v) for k, v in fields_dict.items())

class ConsoleUI:
    @staticmethod
    def clear_screen() -> None:
        os.system('clear' if os.name == 'posix' else 'cls')

    @staticmethod
    def draw_box(title: str, lines: List[str], border_color: str, title_color: str = Config.C_, box_width: int = 95) -> None:
        print(f"{border_color}┌" + "─" * (box_width - 2) + f"┐{Config.S_}")
        title_str = f" {title} "
        left_pad = (box_width - 2 - len(title_str)) // 2
        right_pad = box_width - 2 - len(title_str) - left_pad
        print(f"{border_color}│{Config.S_}" + " " * left_pad + f"{title_color}{Config.B_}{title_str}{Config.S_}" + " " * right_pad + f"{border_color}│{Config.S_}")
        print(f"{border_color}├" + "─" * (box_width - 2) + f"┤{Config.S_}")
        
        ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
        for line in lines:
            clean_line = ansi_escape.sub('', line)
            visible_len = len(clean_line)
            padding = max(0, box_width - 4 - visible_len)
            print(f"{border_color}│ {Config.S_}{line}" + " " * padding + f" {border_color}│{Config.S_}")
        print(f"{border_color}└" + "─" * (box_width - 2) + f"┘{Config.S_}")

    @classmethod
    def display_banner(cls) -> None:
        cls.clear_screen()
        ascii_art = f"""{Config.C_}{Config.B_}
██████╗ ██╗██╗  ██╗ ██████╗ ██████╗ 
██╔══██╗██║╚██╗██╔╝██╔═══██╗██╔══██╗
██████╔╝██║ ╚███╔╝ ██║   ██║██████╔╝
██╔══██╗██║ ██╔██╗ ██║   ██║██╔══██╗
██║  ██║██║██╔╝ ██╗╚██████╔╝██║  ██║
╚═╝  ╚═╝╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝
{Config.S_}"""
        print(ascii_art)
        dev_info = [
            f" {Config.C_}Creator {Config.S_}: {Config.W_}Rixor{Config.S_}",
            f" {Config.C_}Version {Config.S_}: {Config.W_}PRO V2 (OB55 Updated){Config.S_}",
            f" {Config.C_}Contact {Config.S_}: {Config.W_}@rakibz4{Config.S_}",
            f" {Config.C_}Channel {Config.S_}: {Config.W_}https://t.me/rixorchat{Config.S_}"
        ]
        cls.draw_box("SYSTEM INFO", dev_info, Config.C_, Config.C_)
        print()

    @staticmethod
    def show_registration_success(curr_count: int, target: int, name: str, uid: str, pwd: str, acc_id: str, region: str) -> None:
        with state.print_lock:
            curr_time = datetime.now().strftime("%I:%M:%S %p")
            c_ = Config.C_
            s_ = Config.S_
            b_ = Config.B_
            w_ = Config.W_
            
            print(f" {c_}┌─────────────────────────────────────────────────────────────────────────────────────────────┐{s_}")
            title_txt = f"▶ ACCOUNT {curr_count} / {target}"
            title_pad = 91 - len(title_txt)
            print(f" {c_}│{s_} {c_}{b_}{title_txt}{s_}" + " " * title_pad + f"{c_}│{s_}")
            print(f" {c_}├─────────────────────────────────────────────────────────────────────────────────────────────┤{s_}")
            
            def render_row(emoji: str, label: str, value: Any, color: str = w_) -> None:
                v = str(value)
                if len(v) > 52: v = v[:49] + "..."
                pad_len = 76 - len(v)
                print(f" {c_}│{s_} {emoji} {c_}{label:<11}: {color}{v}{s_}" + " " * pad_len + f"{c_}│{s_}")

            render_row("🎮", "Name", name)
            render_row("🆔", "Account ID", acc_id)
            render_row("🔑", "Login UID", uid)
            render_row("🔐", "Password", pwd[:35] + ("..." if len(pwd) > 35 else "")) 
            render_row("🌍", "Server", region)
            render_row("✅", "Status", f"{c_}Successfully Generated{s_}", color="")
            render_row("🕐", "Time", curr_time)
            print(f" {c_}└─────────────────────────────────────────────────────────────────────────────────────────────┘{s_}")

class NetworkService:
    @staticmethod
    def get_rotated_session() -> requests.Session:
        session = requests.Session()
        with state.ip_lock:
            state.ip_counter += 1
            if state.ip_counter >= 20:
                state.ip_counter = 0
                if state.proxy_list:
                    proxy = random.choice(state.proxy_list)
                    session.proxies = {'http': proxy, 'https': proxy}
        return session

class GarenaAPI:
    def __init__(self):
        self.session = NetworkService.get_rotated_session()

    def perform_major_login(self, access_token: str, open_id: str, lang: str) -> Optional[Dict[str, str]]:
        try:
            payload_parts = [
                b'\x1a\x132025-08-30 05:19:21"\tfree fire(\x01:\x081.114.13B2Android OS 9 / API-28 (PI/rel.cjw.20220518.114133)J\x08HandheldR\nATM MobilsZ\x04WIFI`\xb6\nh\xee\x05r\x03300z\x1fARMv7 VFPv3 NEON VMH | 2400 | 2\x80\x01\xc9\x0f\x8a\x01\x0fAdreno (TM) 640\x92\x01\rOpenGL ES 3.2\x9a\x01+Google|dfa4ab4b-9dc4-454e-8065-e70c733fa53f\xa2\x01\x0e105.235.139.91\xaa\x01\x02',
                lang.encode("ascii"),
                b'\xb2\x01 1d8ec0240ede109973f3321b9354b44d\xba\x01\x014\xc2\x01\x08Handheld\xca\x01\x10Asus ASUS_I005DA\xea\x01@afcfbf13334be42036e4f742c80b956344bed760ac91b3aff9b607a610ab4390\xf0\x01\x01\xca\x02\nATM Mobils\xd2\x02\x04WIFI\xca\x03 7428b253defc164018c604a1ebbfebdf\xe0\x03\xa8\x81\x02\xe8\x03\xf6\xe5\x01\xf0\x03\xaf\x13\xf8\x03\x84\x07\x80\x04\xe7\xf0\x01\x88\x04\xa8\x81\x02\x90\x04\xe7\xf0\x01\x98\x04\xa8\x81\x02\xc8\x04\x01\xd2\x04=/data/app/com.dts.freefireth-PdeDnOilCSFn37p1AH_FLg==/lib/arm\xe0\x04\x01\xea\x04_2087f61c19f57f2af4e7feff0b24d9d9|/data/app/com.dts.freefireth-PdeDnOilCSFn37p1AH_FLg==/base.apk\xf0\x04\x03\xf8\x04\x01\x8a\x05\x0232\x9a\x05\n2019118693\xb2\x05\tOpenGLES2\xb8\x05\xff\x7f\xc0\x05\x04\xe0\x05\xf3F\xea\x05\x07android\xf2\x05pKqsHT5ZLWrYljNb5Vqh//yFRlaPHSO9NWSQsVvOmdhEEn7W+VHNUK+Q+fduA3ptNrGB0Ll0LRz3WW0jOwesLj6aiU7sZ40p8BfUE/FI/jzSTwRe2\xf8\x05\xfb\xe4\x06\x88\x06\x01\x90\x06\x01\x9a\x06\x014\xa2\x06\x014\xb2\x06"GQ@O\x00\x0e^\x00D\x06UA\x0ePM\r\x13hZ\x07T\x06\x0cm\\V\x0ejYV;\x0bU5'
            ]
            
            raw_payload = b''.join(payload_parts)
            raw_payload = raw_payload.replace(b'afcfbf13334be42036e4f742c80b956344bed760ac91b3aff9b607a610ab4390', access_token.encode())
            raw_payload = raw_payload.replace(b'1d8ec0240ede109973f3321b9354b44d', open_id.encode())
            
            encrypted_data = bytes.fromhex(SecurityEngine.encrypt_api_payload(raw_payload.hex()))
            
            headers = {
                'User-Agent': "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
                'Accept-Encoding': "deflate, gzip",
                'X-GA-SV': "1789535859",
                'Authorization': "Bearer",
                'X-GA': "v1 1",
                'ReleaseVersion': "OB55",
                'Content-Type': "application/x-www-form-urlencoded",
                'X-Unity-Version': "2018.4.12f1"
            }
            
            resp = self.session.post("https://loginbp.ppmainecoonghj.com/MajorLogin", headers=headers, data=encrypted_data, verify=False, timeout=10)
            
            if resp.status_code == 200:
                jwt_idx = resp.text.find("eyJ")
                if jwt_idx != -1:
                    token = resp.text[jwt_idx:]
                    dot_idx = token.find(".", token.find(".") + 1)
                    if dot_idx != -1:
                        token = token[:dot_idx + 44]
                        payload_b64 = token.split('.')[1]
                        padding = '=' * (4 - len(payload_b64) % 4)
                        decoded_json = json.loads(base64.urlsafe_b64decode(payload_b64 + padding))
                        acc_id = decoded_json.get('account_id') or decoded_json.get('external_id')
                        if acc_id:
                            return {"account_id": str(acc_id), "jwt_token": token}
        except Exception:
            pass
        return None

class AccountGenerator:
    @staticmethod
    def save_to_file(data: Dict[str, Any]) -> None:
        try:
            with state.lock:
                accounts = []
                if os.path.exists(Config.ACCOUNTS_FILE):
                    with open(Config.ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
                        try:
                            file_data = json.load(f)
                            if isinstance(file_data, list): accounts = file_data
                        except Exception: pass
                
                accounts.append({
                    "uid": data["uid"], "password": data["password"],
                    "account_id": data["account_id"], "name": data["name"],
                    "region": data["region"], "date_created": data["date_created"]
                })
                
                with open(Config.ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(accounts, f, indent=4, ensure_ascii=False)
        except Exception: pass

    @classmethod
    def execute_creation(cls, region: str, prefix: str) -> Optional[Dict[str, Any]]:
        for _ in range(5):
            if state.exit_flag: return None
            try:
                api = GarenaAPI()
                password = SecurityEngine.generate_ultra_secure_password()
                
                reg_payload = json.dumps({"app_id": 100067, "client_type": 2, "password": password, "source": 2}, separators=(',', ':'))
                headers_reg = {
                    "User-Agent": "GarenaMSDK/4.0.44(25028RN03A ;Android 15;ar;EG;app 1.132.1 2019121229;)",
                    "Connection": "Keep-Alive", "Accept": "application/json", "Accept-Encoding": "gzip",
                    "Authorization": f"Signature {SecurityEngine.generate_signature(reg_payload)}",
                    "Content-Type": "application/json; charset=utf-8",
                    "Cookie": "datadome=oYpIhVco_RFvLHe_T9KFd5wuY0gcQuNfrlt4rHJY5QOkwv4TGt8gPMK32MbHuBdzJyfXnXlfzNZT_2tHr2kys8AMYT2~T71QP1S78_7Pdx4JLOXdSrflPT6cOX2vsyJh",
                    "Host": "100067.connect.garena.com",
                }
                
                resp_reg = api.session.post("https://100067.connect.garena.com/api/v2/oauth/guest:register", headers=headers_reg, data=reg_payload, timeout=10, verify=False)
                if resp_reg.status_code != 200 or resp_reg.json().get("code") != 0: continue
                uid = resp_reg.json()['data']['uid']
                
                tok_payload = json.dumps({
                    "client_id": 100067, "client_secret": Config.API_HEX_KEY, "client_type": 2, 
                    "device_id": "02-344afb0e-593c-40b7-92f2-171972f74807", "password": password, 
                    "response_type": "token", "uid": uid,
                }, separators=(',', ':'))
                
                headers_tok = headers_reg.copy()
                headers_tok["Cookie"] = "datadome=y23Z3X17pgkMHEt5zY8dqxC6BIf7WJMgC0RXNbqifHT7t9zajKe_hegFb1Ie9_7JixXpz7FRGVodOn~mWPk_NrqIIhUOXDYqKOahzoRQcyEy77GWEMcdA9_MqPJeM5qv"
                
                resp_tok = api.session.post("https://100067.connect.garena.com/api/v2/oauth/guest/token:grant", headers=headers_tok, data=tok_payload, timeout=10, verify=False)
                if resp_tok.status_code != 200 or resp_tok.json().get("code") != 0: continue
                
                access_token = resp_tok.json()['data']['access_token']
                open_id = resp_tok.json()['data']['open_id']

                keystream = [0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30]
                field = codecs.decode(''.join(chr(ord(open_id[i]) ^ keystream[i % len(keystream)]) for i in range(len(open_id))).encode('unicode_escape').decode('utf-8'), 'unicode_escape').encode('latin1')
                
                name = f"{prefix}{random.randint(10000, 99999)}"
                lang = Config.REGION_LANG.get(region.upper(), "en")
                
                proto = ProtoBuilder.build({1: name, 2: access_token, 3: open_id, 5: 102000007, 6: 4, 7: 1, 13: 1, 14: field, 15: lang, 16: 1, 17: 1})
                enc_major = bytes.fromhex(SecurityEngine.encrypt_api_payload(proto.hex()))
                
                headers_major = {
                    "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
                    "Accept-Encoding": "deflate, gzip", "X-GA-SV": "1789535859", "Authorization": "Bearer",
                    "X-GA": "v1 1", "ReleaseVersion": "OB55", "Content-Type": "application/x-www-form-urlencoded",
                    "X-Unity-Version": "2018.4.12f1", "Host": "loginbp.ppmainecoonghj.com"
                }
                api.session.post("https://loginbp.ppmainecoonghj.com/MajorRegister", headers=headers_major, data=enc_major, verify=False, timeout=10)
                
                login_data = api.perform_major_login(access_token, open_id, lang)
                if login_data:
                    account_record = {
                        "uid": int(uid), "password": password, "account_id": login_data["account_id"],
                        "name": name, "region": region, "date_created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    cls.save_to_file(account_record)
                    return account_record
            except Exception: pass
        return None

def worker_task(region: str, prefix: str, target: int) -> None:
    while not state.exit_flag:
        with state.lock:
            if state.success_count >= target: break
            
        acc = AccountGenerator.execute_creation(region, prefix)
        if acc:
            with state.lock:
                if state.success_count >= target: break
                state.success_count += 1
                curr_count = state.success_count
                
            ConsoleUI.show_registration_success(curr_count, target, acc['name'], acc['uid'], acc['password'], acc['account_id'], acc['region'])

def shutdown_handler(signum, frame):
    print(f"\n{Config.C_}[!] Stopping gracefully...{Config.S_}")
    state.exit_flag = True
    sys.exit(0)

try:
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
except ValueError:
    pass

def run_application():
    ConsoleUI.display_banner()
    
    server_menu = {
        "1": "BD", "2": "IND", "3": "PK", "4": "SG",
        "5": "ID", "6": "ME"
    }
    
    menu_lines = [
        f" {Config.C_}[1] {Config.W_}BD (Bangladesh)     {Config.C_}[2] {Config.W_}IND (India)       {Config.C_}[3] {Config.W_}PK (Pakistan){Config.S_}",
        f" {Config.C_}[4] {Config.W_}SG (Singapore)      {Config.C_}[5] {Config.W_}ID (Indonesia)    {Config.C_}[6] {Config.W_}ME (Middle East){Config.S_}"
    ]
    
    ConsoleUI.draw_box("SERVER SELECTION (1-6)", menu_lines, Config.C_, Config.C_)
    
    choice = input(f"\n{Config.C_}>> Select Server (1-6) : {Config.W_}").strip().lower()
    if choice not in server_menu:
        print(f"\n{Fore.RED}Err - Invalid server{Config.S_}")
        return
        
    region = server_menu[choice]
    prefix = input(f"{Config.C_}>> Name Prefix        : {Config.W_}").strip()
    
    try:
        target = int(input(f"{Config.C_}>> Amount to Generate : {Config.W_}"))
        threads_count = 52
    except ValueError:
        print(f"\n{Fore.RED}Err - Invalid amount{Config.S_}")
        return

    print(f"\n{Config.C_}INITIALIZING ENGINE WITH {threads_count} THREADS FOR {region} SERVER...{Config.S_}\n")
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=threads_count) as executor:
        futures = [executor.submit(worker_task, region, prefix, target) for _ in range(threads_count)]
        try:
            while any(f.running() for f in futures):
                time.sleep(0.1)
                with state.lock:
                    if state.success_count >= target:
                        break
        except KeyboardInterrupt:
            shutdown_handler(None, None)

    elapsed = time.time() - start_time
    print(f"\n{Config.C_}========================================================================================={Config.S_}")
    print(f"{Config.C_}{Config.B_}                        Generation Summary Report{Config.S_}")
    print(f"{Config.C_}========================================================================================={Config.S_}")
    print(f" {Config.C_}Target Accounts : {Config.W_}{target}{Config.S_}")
    print(f" {Config.C_}Successful      : {Config.W_}{state.success_count}{Config.S_}")
    print(f" {Config.C_}Time Elapsed    : {Config.W_}{elapsed:.2f} seconds{Config.S_}")
    print(f"{Config.C_}========================================================================================={Config.S_}\n")

if __name__ == "__main__":
    run_application()
