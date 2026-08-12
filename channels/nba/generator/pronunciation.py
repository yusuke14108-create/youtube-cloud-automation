import re

READINGS = {"河村勇輝": "かわむら ゆうき", "八村塁": "はちむら るい", "富永啓生": "とみなが けいせい", "渡邊雄太": "わたなべ ゆうた", "渡辺雄太": "わたなべ ゆうた"}

def for_speech(text: str) -> str:
    for written, reading in sorted(READINGS.items(), key=lambda item: len(item[0]), reverse=True):
        text = text.replace(written, reading)
    return text.replace("NBA", "エヌビーエー")
