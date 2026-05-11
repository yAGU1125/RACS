import time
import nfc

def on_connect(tag):
    print("\nカードがタッチされました！")
    
    # カードのタイプ名を取得
    card_type = tag.type
    
    try:
        # ほとんどのカード（Type2, Type3, Type4）は tag.identifier をサポートしています
        # 大文字の16進数文字列に変換します
        card_id = tag.identifier.hex().upper()
        
        print(f"✅ カードタイプ: {card_type}")
        print(f"✅ 読み取った物理 ID: {card_id}")
        
    except Exception as e:
        print(f"❌ カードタイプは {card_type} ですが、物理 ID を読み取れません。原因: {e}")
    
    return True

def main():
    print("カードリーダーを初期化中...")
    try:
        clf = nfc.ContactlessFrontend("usb")
        print("===================================")
        print("準備完了！任意の NFC カードをタッチしてください...")
        print("（交通系ICカード/学生証/クレジットカード/入退室用ICタグ などに対応）")
        print("Ctrl+C を押すとプログラムを終了します")
        print("===================================")
        
        while True:
            clf.connect(rdwr={'on-connect': on_connect})
            time.sleep(1)
            
    except Exception as e:
        print(f"カードリーダーの接続に失敗しました: {e}")

if __name__ == "__main__":
    main()