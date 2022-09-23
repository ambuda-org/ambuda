from dataclasses import dataclass


@dataclass
class Locale:
    code: str
    slug: str
    text: str


TEXT_CATEGORIES = {
    "itihasa": [
        "ramayanam",
        "mahabharatam",
    ],
    "kavya": [
        "amarushatakam",
        "kiratarjuniyam",
        "kumarasambhavam",
        "kokilasandesha",
        "caurapancashika",
        "bhattikavyam",
        "meghadutam-kale",
        "mukundamala",
        "raghuvamsham",
        "shatakatrayam",
        "shishupalavadham",
        "saundaranandam",
        "hamsadutam",
    ],
    "upanishat": ["shivopanishat"],
    "anye": [
        "bodhicaryavatara",
        "catuhshloki",
    ],
}


BOT_USERNAME = "ambuda-bot"


LOCALES = [
    Locale(code="sa", slug="sa", text="संस्कृतम्"),
    Locale(code="en", slug="en", text="English"),
    Locale(code="mr_IN", slug="mr", text="मराठी"),
    Locale(code="te_IN", slug="te", text="తెలుగు"),
]
