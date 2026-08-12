READINGS = {"SFTS": "エスエフティーエス", "COVID-19": "新型コロナウイルス感染症"}

def for_speech(text: str) -> str:
    for written, reading in sorted(READINGS.items(), key=lambda item: len(item[0]), reverse=True):
        text = text.replace(written, reading)
    return text
