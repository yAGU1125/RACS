import csv
# ================= Anrdoidデバイス専用 =================
# import sys
# if sys.platform == 'android':
#     sys.platform = 'linux'
# =========================================
import os
import threading
import time
import re
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template_string
import requests
import asyncio
import discord
from discord.ext import commands

import nfc
import nfc.tag.tt3

# ================= 設定エリア =================
WEBHOOK_URL = "" #ここにチャンネルWEBHOOKURL
DISCORD_BOT_TOKEN = "" #ここにロボットURL
CSV_FILE_PATH = "simple.csv" #ここに参考するCSVファイル
# =========================================

app = Flask(__name__)

users_state = {}
app_state = {
    "mode": "enter",
    "last_message": "準備完了",
    "last_scan_time": ""
}

# 全員の詳細情報を一括で読み込むためのグローバルデータ辞書
USER_DATA = {}

def load_user_data():
    global USER_DATA
    if os.path.isfile(CSV_FILE_PATH):
        with open(CSV_FILE_PATH, "r", newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            for row in reader:
                USER_DATA[row["id"]] = {
                    "name": row.get("name", "不明"),
                    "class": row.get("クラス名列", ""),
                    "role": row.get("役職", ""),
                    "department": row.get("所属部門", ""),
                    "team": row.get("所属チーム", ""),
                    "grade": row.get("学年", ""),
                    "major": row.get("専攻学科", "") # バグ修正済: 「・」を追加
                }
# プログラム起動時に一度だけCSVデータをメモリに読み込む
load_user_data()

# --- Discord Bot設定 ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

@bot.event
async def on_ready():
    print(f"=====================================")
    print(f"🟢 Discord Bot ログイン成功: {bot.user}")
    print(f"=====================================")

@bot.event
async def on_message(message):
    # Bot自身が送信したメッセージに返信しないようにする
    if message.author == bot.user:
        return
        
    text = message.content.strip()
    
    # 標準の /在室人数 などのスラッシュコマンドを引き続き有効にする
    await bot.process_commands(message)
    
    # ================= カスタム自然言語検索機能 =================
    
    # 1. "xxxの在室人数"の処理 (例: 情報工学専攻の在室人数, B4の在室人数)
    if text.endswith("の在室人数"):
        keyword = text.replace("の在室人数", "").strip()
        # スマートあいまい処理: 一般的な接尾辞を削除。例：「イベントチーム」を検索すると自動的に「イベント」に変換して照合
        search_kw = keyword.replace("チーム", "").replace("部門", "").replace("学科", "").replace("専攻", "")
        
        in_users = []
        for uid, state in users_state.items():
            if state["status"] == "in":
                info = USER_DATA.get(uid, {})
                # 該当キーワードが 学年、専攻、チーム、部門 のいずれかに一致するか確認
                if (search_kw in str(info.get("grade", "")) or 
                    search_kw in str(info.get("major", "")) or 
                    search_kw in str(info.get("team", "")) or 
                    search_kw in str(info.get("department", ""))):
                    in_users.append(info.get("name", "不明"))
                    
        count = len(in_users)
        if count == 0:
            await message.channel.send(f"現在、{keyword}の人は誰もいません。")
        else:
            msg = f"📊 **{keyword} の在室人数: {count}人**\n"
            for name in in_users:
                msg += f"・{name}\n"
            await message.channel.send(msg)

    role_match = re.search(r'^(.+)の在室確認$', text)
    if role_match:
        role_keyword = role_match.group(1).strip()
        
        in_users = []
        for uid, state in users_state.items():
            if state["status"] == "in":
                info = USER_DATA.get(uid, {})
                # 役職列を確認 (複数の役職の照合に対応。例: "プロジェクトリーダー, 運営リーダー")
                if role_keyword in str(info.get("role", "")):
                    in_users.append(info.get("name", "不明"))
                    
        count = len(in_users)
        if count == 0:
            await message.channel.send(f"現在、**{role_keyword}** の人は誰もいません。")
        else:
            msg = f"🛡️ **{role_keyword} の在室確認: {count}人**\n"
            for name in in_users:
                msg += f"・{name}\n"
            await message.channel.send(msg)
    # ==========================================================

@bot.command(name="在室人数")
async def check_in_room(ctx):
    in_room_users = [info["name"] for uid, info in users_state.items() if info["status"] == "in"]
    count = len(in_room_users)
    
    if count == 0:
        await ctx.send("現在、教室には誰もいません。")
        return
        
    msg = f"👥 **全体の在室人数: {count}人**\n"
    for name in in_room_users:
        msg += f"・{name}\n"
        
    await ctx.send(msg)

# ================= 開発者デバッグツール =================
# @bot.command(name="SC")
# async def simulate_scan(ctx, *, identifier: str):
#     """
#     開発テスト用: 名前またはIDを入力して物理的なスキャンをシミュレートする
#     使い方: /SC 宮﨑 陽向   または   /SC 1209208
#     """
#     target_id = None
    
#     # 1. まず入力されたものをIDとして直接検索を試みる
#     if identifier in USER_DATA:
#         target_id = identifier
#     else:
#         # 2. IDでない場合は、名簿をループして名前を照合する
#         # 注意: 照合しやすいように、ここで入力テキストのスペースを削除する
#         search_name = identifier.replace(" ", "").replace("　", "")
#         for uid, info in USER_DATA.items():
#             if info["name"].replace(" ", "").replace("　", "") == search_name:
#                 target_id = uid
#                 break

#     if target_id:
#         name = USER_DATA[target_id]["name"]
#         # スキャン処理関数を直接呼び出し、物理的なスキャンプロセスを完全に再現する
#         handle_scan(target_id)
#         await ctx.send(f"🔧 **[開発テスト]** `{name}` (ID: {target_id}) のスキャンをシミュレートしました。")
#     else:
#         await ctx.send(f"❌ **[エラー]** '{identifier}' という名前またはIDが名簿に見つかりません。")
# ==================================================

def run_discord_bot():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        bot.run(DISCORD_BOT_TOKEN)
    except Exception as e:
        print(f"🔴 Discord Bot 起動失敗: {e}")
# -----------------------------------------

def send_discord_message(msg):
    if WEBHOOK_URL.startswith("http"):
        try:
            requests.post(WEBHOOK_URL, json={"content": msg}, timeout=5)
        except:
            pass

def load_user_name(tag_id):
    # メモリ内の辞書から高速に名前を読み取るように変更
    if tag_id in USER_DATA:
        return USER_DATA[tag_id]["name"]
    return "不明"

def clean_old_logs():
    now = datetime.now()
    for filename in os.listdir('.'):
        if filename.startswith("log_") and filename.endswith(".csv"):
            date_str = filename[4:12]
            try:
                log_date = datetime.strptime(date_str, "%Y%m%d")
                if (now - log_date).days > 7:
                    os.remove(filename)
            except ValueError:
                pass

def log_scan(tag_id, name, action):
    today = datetime.now().strftime("%Y%m%d")
    log_filename = f"log_{today}.csv"
    file_exists = os.path.isfile(log_filename)
    with open(log_filename, "a", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["日時", "学籍番号/ID", "氏名", "アクション"])
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        writer.writerow([timestamp, tag_id, name, action])

class NFCReaderThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.daemon = True

    def run(self):
        clf = nfc.ContactlessFrontend("usb")
        while True:
            try:
                clf.connect(rdwr={"on-connect": self.on_connect})
            except:
                time.sleep(1)

    def on_connect(self, tag):
        try:
            tag_id = None
            if tag.type == 'Type3Tag':
                try:
                    sc = nfc.tag.tt3.ServiceCode(0x200B >> 6, 0x200B & 0x3F)
                    bc = nfc.tag.tt3.BlockCode(0, service=0)
                    data = tag.read_without_encryption([sc], [bc])
                    decoded_id = data[0:8].decode("utf-8")
                    if decoded_id.isdigit():
                        tag_id = decoded_id
                except Exception:
                    pass
            if not tag_id:
                tag_id = tag.identifier.hex().upper()

            handle_scan(tag_id)
        except Exception as e:
            pass
        return True

def handle_scan(tag_id):
    name = load_user_name(tag_id)
    if tag_id not in users_state:
        users_state[tag_id] = {"status": "out", "name": name}
    current_status = users_state[tag_id]["status"]
    mode = app_state["mode"]
    action_text = ""
    if mode == "enter":
        if current_status == "in":
            msg = f"{name}さんが再び入室しました。次回は退室時のスキャンを忘れないでください。"
            app_state["last_message"] = f"再入室: {name}"
            action_text = "再入室"
        else:
            msg = f"{name}さんが入室しました。"
            users_state[tag_id]["status"] = "in"
            app_state["last_message"] = f"入室: {name}"
            action_text = "入室"
        send_discord_message(msg)
    elif mode == "exit":
        if current_status == "out":
            app_state["last_message"] = f"既におりません: {name}"
            action_text = "退室エラー(未入室)"
        else:
            msg = f"{name}さんが退室しました。"
            users_state[tag_id]["status"] = "out"
            app_state["last_message"] = f"退室: {name}"
            action_text = "退室"
            send_discord_message(msg)
    users_state[tag_id]["name"] = name
    app_state["last_scan_time"] = datetime.now().strftime("%H:%M:%S")
    if action_text:
        log_scan(tag_id, name, action_text)

def midnight_reset_loop():
    while True:
        now = datetime.now()
        if now.hour == 0 and now.minute == 0:
            for uid in users_state:
                users_state[uid]["status"] = "out"
            app_state["last_message"] = "深夜リセット完了"
            clean_old_logs()
            time.sleep(60)
        time.sleep(30)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>サークル入退室管理</title>
    <style>
        body { font-family: sans-serif; text-align: center; background-color: #f4f4f9; margin: 0; padding: 20px; }
        .container { max-width: 500px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        h1 { font-size: 24px; color: #333; }
        .toggle-btn { display: inline-block; width: 45%; padding: 20px; font-size: 22px; font-weight: bold; border: none; border-radius: 8px; cursor: pointer; margin: 5px; transition: 0.2s; }
        .btn-enter { background-color: #e0e0e0; color: #777; }
        .btn-enter.active { background-color: #4CAF50; color: white; box-shadow: 0 4px 0 #388E3C; transform: translateY(-2px); }
        .btn-exit { background-color: #e0e0e0; color: #777; }
        .btn-exit.active { background-color: #f44336; color: white; box-shadow: 0 4px 0 #D32F2F; transform: translateY(-2px); }
        .status-box { margin: 20px 0; padding: 15px; background-color: #e3f2fd; border-radius: 8px; font-size: 20px; font-weight: bold; color: #1565c0; min-height: 28px; }
        .list-container { text-align: left; margin-top: 20px; }
        ul { list-style-type: none; padding: 0; }
        li { background: #eee; margin: 8px 0; padding: 12px; border-radius: 5px; font-size: 20px; font-weight: bold; color: #333; }
    </style>
</head>
<body>
    <div class="container">
        <h1>入退室管理</h1>
        <div>
            <button id="btn-enter" class="toggle-btn btn-enter" onclick="setMode('enter')">入室</button>
            <button id="btn-exit" class="toggle-btn btn-exit" onclick="setMode('exit')">退室</button>
        </div>
        <div class="status-box" id="status-message">準備完了</div>
        <div class="list-container">
            <h3>現在の入室者: <span id="count">0</span>人</h3>
            <ul id="in-room-list"></ul>
        </div>
    </div>
    <script>
        function setMode(mode) {
            fetch('/api/mode', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({mode: mode})
            }).then(() => updateUI());
        }
        function updateUI() {
            fetch('/api/state')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('btn-enter').className = 'toggle-btn btn-enter ' + (data.mode === 'enter' ? 'active' : '');
                    document.getElementById('btn-exit').className = 'toggle-btn btn-exit ' + (data.mode === 'exit' ? 'active' : '');
                    let msg = data.last_message;
                    if(data.last_scan_time) msg += ' (' + data.last_scan_time + ')';
                    document.getElementById('status-message').innerText = msg;
                    const list = document.getElementById('in-room-list');
                    list.innerHTML = '';
                    let count = 0;
                    data.in_room.forEach(name => {
                        let li = document.createElement('li');
                        li.innerText = name;
                        list.appendChild(li);
                        count++;
                    });
                    document.getElementById('count').innerText = count;
                });
        }
        setInterval(updateUI, 1000);
        updateUI();
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/state", methods=["GET"])
def get_state():
    in_room = [info["name"] for uid, info in users_state.items() if info["status"] == "in"]
    return jsonify({
        "mode": app_state["mode"],
        "last_message": app_state["last_message"],
        "last_scan_time": app_state["last_scan_time"],
        "in_room": in_room
    })

@app.route("/api/mode", methods=["POST"])
def set_mode():
    data = request.json
    if data and "mode" in data and data["mode"] in ["enter", "exit"]:
        app_state["mode"] = data["mode"]
    return jsonify({"success": True})

if __name__ == "__main__":
    clean_old_logs()
    threading.Thread(target=run_discord_bot, daemon=True).start()
    threading.Thread(target=midnight_reset_loop, daemon=True).start()
    nfc_thread = NFCReaderThread()
    nfc_thread.start()
    app.run(host="0.0.0.0", port=5000)