DATABASE = {
    "English": {
        "HELLO": "Hello",
        "THANK YOU": "Thank you",
        "YES": "Yes",
        "NO": "No",
        "HELP": "Help",
        "PLEASE": "Please",
        "EMERGENCY_MSG": "Emergency! This person needs help."
    },
    "Hindi": {
        "HELLO": "नमस्ते",
        "THANK YOU": "धन्यवाद",
        "YES": "हाँ",
        "NO": "नहीं",
        "HELP": "मदद",
        "PLEASE": "कृपया",
        "EMERGENCY_MSG": "आपातकाल! इस व्यक्ति को मदद की जरूरत है।"
    },
    "Gujarati": {
        "HELLO": "નમસ્તે",
        "THANK YOU": "આભાર",
        "YES": "હા",
        "NO": "ના",
        "HELP": "મદદ",
        "PLEASE": "કૃપા કરી",
        "EMERGENCY_MSG": "કટોકટી! આ વ્યક્તિને મદદની જરૂર છે."
    }
}

def get_translation(gesture_key, language="English"):
    """Fetch localized translated output context string equivalent to gesture pattern."""
    lang_dict = DATABASE.get(language, DATABASE["English"])
    return lang_dict.get(gesture_key, gesture_key)
