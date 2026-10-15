"""Patient-facing replies. Built ONLY from these fixed templates plus stored, approved
data (memory titles, routine titles, activity titles) — never from model free text.

English is the reviewed baseline. hi/as/bn strings are DRAFTS pending native-speaker
review; missing keys fall back to English.
"""

from app.models.enums import Language

EN = {
    "safety": "I'm sorry you feel this way. Please call a family member now. "
    "If it is an emergency, call 112.",
    "stop": "All right, we can stop now. Thank you for spending time with me.",
    "fatigue": "Let's take a little rest. We can do something gentle later.",
    "greeting": "Hello! It's good to talk with you.",
    "farewell": "Goodbye! Talk to you soon.",
    "time": "It is {time}.",
    "date": "Today is {date}.",
    "routine_next": "Next: {title} at {time}.",
    "routine_none": "There is nothing else planned for today.",
    "memory": "That reminds me of “{title}”.",
    "which_person": "Who do you mean? You can show me a photo.",
    "which_place": "Which place do you mean?",
    "which_routine": "Which part of your day do you mean?",
    "unclear": "I'm not sure I understood. "
    "Would you like to do an activity or talk about your family?",
    "suggest": "Would you like to try “{title}”?",
    "candidate": "That sounds special. Shall I ask your family to add it to your memories?",
}

# DRAFT translations (not yet reviewed by native speakers).
DRAFTS: dict[Language, dict[str, str]] = {
    Language.HINDI: {
        "safety": "मुझे दुख है कि आप ऐसा महसूस कर रहे हैं। कृपया अभी परिवार के किसी सदस्य को फ़ोन करें। "
        "आपातकाल में 112 पर कॉल करें।",
        "stop": "ठीक है, अब हम रुक सकते हैं। मेरे साथ समय बिताने के लिए धन्यवाद।",
        "fatigue": "चलिए थोड़ा आराम करते हैं।",
        "greeting": "नमस्ते! आपसे बात करके अच्छा लगा।",
        "farewell": "फिर मिलेंगे!",
    },
    Language.ASSAMESE: {
        "safety": "আপুনি এনে অনুভৱ কৰিছে বুলি মই দুখিত। অনুগ্ৰহ কৰি এতিয়াই পৰিয়ালৰ কাৰোবাক ফোন কৰক। "
        "জৰুৰীকালীন অৱস্থাত 112 ত ফোন কৰক।",
        "stop": "ঠিক আছে, এতিয়া আমি ৰখিব পাৰো।",
        "fatigue": "অলপ জিৰণি লওঁ আহক।",
        "greeting": "নমস্কাৰ! আপোনাৰ সৈতে কথা পাতি ভাল লাগিল।",
    },
    Language.BENGALI: {
        "safety": "আপনার এমন লাগছে শুনে আমি দুঃখিত। দয়া করে এখনই পরিবারের কাউকে ফোন করুন। "
        "জরুরি অবস্থায় 112-এ ফোন করুন।",
        "stop": "ঠিক আছে, এখন আমরা থামতে পারি।",
        "fatigue": "চলুন একটু বিশ্রাম নিই।",
        "greeting": "নমস্কার! আপনার সাথে কথা বলে ভালো লাগলো।",
    },
}


def text(language: Language, key: str, **values: str) -> str:
    template = DRAFTS.get(language, {}).get(key) or EN[key]
    return template.format(**values)
