import re

READINGS = {"大谷翔平": "おおたにしょうへい", "山本由伸": "やまもとよしのぶ", "佐々木朗希": "ささきろうき", "鈴木誠也": "すずきせいや", "今永昇太": "いまながしょうた", "千賀滉大": "せんがこうだい", "ダルビッシュ有": "ダルビッシュゆう", "菊池雄星": "きくちゆうせい", "吉田正尚": "よしだまさたか"}

def for_speech(text: str) -> str:
    for written, reading in sorted(READINGS.items(), key=lambda item: len(item[0]), reverse=True):
        text = text.replace(written, reading)
    return text.replace("MLB", "メジャーリーグ")
