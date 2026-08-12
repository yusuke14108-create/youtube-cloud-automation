import re

READINGS = {"河村勇輝": "かわむらゆうき", "八村塁": "はちむらるい", "富永啓生": "とみながけいせい", "渡邊雄太": "わたなべゆうた", "渡辺雄太": "わたなべゆうた"}

def for_speech(text: str) -> str:
    for written, reading in sorted(READINGS.items(), key=lambda item: len(item[0]), reverse=True):
        text = text.replace(written, reading)
    return text.replace("NBA", "エヌビーエー")
