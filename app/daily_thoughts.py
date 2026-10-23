"""The "Thought for today" on the daily panchang card: one short, positive line drawn from the day's panchang.

A festival's own thought comes first, then the special tithis (Ekadashi, Pradosh, Purnima, Amavasya, Chaturthi,
Ashtami), then the nakshatra at sunrise, whose deity and nature every line follows. Written by hand, not generated,
so a card that goes out to thousands never says anything odd; paraphrases, not scripture quotes.
"""
from __future__ import annotations

# Matched by the start of the festival's name, in this order
FESTIVAL = [
    ("Diwali", "Light one lamp inside before you light a hundred outside.", "Diwali"),
    ("Dhanteras", "Good health is the first wealth. Buy something small, give something big.", "Dhanteras"),
    ("Govardhan", "Like Krishna lifting the hill, help carry the load of those around you.", "Govardhan Puja"),
    ("Bhai Dooj", "Look after each other always. A sibling is a friend for life.", "Bhai Dooj"),
    ("Chhath", "Thank the setting Sun and the rising Sun. Both give us life.", "Chhath Puja"),
    ("Karva Chauth", "Love is patience. Waiting together makes the bond stronger.", "Karva Chauth"),
    ("Raksha Bandhan", "A thread tied with love is stronger than any chain.", "Raksha Bandhan"),
    ("Krishna Janmashtami", "Do your duty with love, and leave the result to Krishna.", "Janmashtami"),
    ("Ganesh Chaturthi", "Welcome Ganesha with a humble heart, and obstacles melt away.", "Ganesh Chaturthi"),
    ("Maha Shivaratri", "Stay awake within. In stillness, Shiva is found.", "Maha Shivaratri"),
    ("Holika Dahan", "Throw one old grudge into tonight’s fire. Faith outlasts the flames.", "Holika Dahan"),
    ("Holi", "Let the colours wash away old quarrels. Hug someone you have missed.", "Holi"),
    ("Hola Mohalla", "Strength with discipline, courage with kindness: that is the Khalsa way.", "Hola Mohalla"),
    ("Ram Navami", "Walk the right path even when it is hard. That is Rama’s way.", "Ram Navami"),
    ("Hanuman Jayanti", "With devotion, the impossible becomes one leap. Serve without ego.", "Hanuman Jayanti"),
    ("Dussehra", "Good always wins in the end. Conquer one weakness of your own today.", "Dussehra"),
    ("Sharad Navratri", "Nine nights to grow stronger. Begin with one good habit today.", "Sharad Navratri"),
    ("Chaitra Navratri", "A new year begins. Plant one good intention and tend it daily.", "Chaitra Navratri"),
    ("Akshaya Tritiya", "What you give today never runs out. Begin with charity.", "Akshaya Tritiya"),
    ("Sharad Purnima", "Tonight the Moon is at its brightest. Let your heart be as clear.", "Sharad Purnima"),
    ("Kartik Purnima", "A lamp on the water, a prayer in the heart. Let your light travel far.", "Kartik Purnima"),
    ("Guru Purnima", "Bow to every teacher who lit your way, and become one for someone.", "Guru Purnima"),
    ("Vasant Panchami", "Learn something new today. Saraswati blesses the curious mind.", "Vasant Panchami"),
    ("Nag Panchami", "Respect every living being. All of nature is one family.", "Nag Panchami"),
    ("Makara Sankranti", "The Sun turns north. Share sweets, and let the sweetness stay.", "Makara Sankranti"),
    ("Lohri", "Gather round the fire, share the harvest, and give thanks together.", "Lohri"),
    ("Vaisakhi", "Stand up for what is right, and share what you have.", "Vaisakhi"),
    ("Prakash Purab", "Remember God, earn honestly, and share with others.", "Gurpurab"),
    ("Gurgaddi Divas", "Let the Guru’s word be your guide in every step.", "Gurgaddi Divas"),
    ("Shaheedi Purab", "Courage is standing firm for others’ freedom, as the Gurus did.", "Shaheedi Purab"),
    ("Bandi Chhor", "Freedom is sweeter when shared. Light a lamp for everyone’s release.", "Bandi Chhor Divas"),
]

# By tithi number (1-30), the days people keep a vrat or puja
TITHI = {
    11: ("Eat a little less today, and listen a little more.", "Ekadashi · Lord Vishnu"),
    26: ("Eat a little less today, and listen a little more.", "Ekadashi · Lord Vishnu"),
    13: ("At sunset, pause. Let the day go and bow to what is greater.", "Pradosh · Lord Shiva"),
    28: ("At sunset, pause. Let the day go and bow to what is greater.", "Pradosh · Lord Shiva"),
    15: ("The full Moon shares its light with everyone. Give freely today.", "Purnima"),
    30: ("On the darkest night, light a lamp for your ancestors and say thank you.", "Amavasya"),
    4: ("Ask Ganesha to clear the path, then take the first step yourself.", "Chaturthi · Lord Ganesha"),
    19: ("Ask Ganesha to clear the path, then take the first step yourself.", "Sankashti Chaturthi · Ganesha"),
    8: ("Courage is quiet. Face one fear today with a steady heart.", "Ashtami · Maa Durga"),
}

# The 27 nakshatras: the thought, and its deity as the source line
NAKSHATRA = {
    "Ashwini": ("Begin gently and heal quickly. A small fresh start is enough.", "the Ashwini Kumaras, healers"),
    "Bharani": ("Carry only what is yours to carry. Set the rest down with grace.", "Yama"),
    "Krittika": ("Let your fire cook, not burn. Speak the truth, and speak it kindly.", "Agni, fire"),
    "Rohini": ("Grow something beautiful today: a plant, a skill or a friendship.", "Brahma, the creator"),
    "Mrigashira": ("Stay curious. The searching mind finds what the busy mind misses.", "Soma, the Moon"),
    "Ardra": ("After the storm the air is clear. Let today’s tears wash, not wound.", "Rudra, the storm"),
    "Punarvasu": ("Come home to yourself. Every day can be a fresh beginning.", "Aditi, mother of the gods"),
    "Pushya": ("Nourish someone today. What you feed in others grows in you.", "Brihaspati, the teacher"),
    "Ashlesha": ("Hold on to wisdom, let go of grudges. Shed what you have outgrown.", "the Nagas"),
    "Magha": ("Remember those who came before you. Their blessings walk with you.", "the Pitris, our ancestors"),
    "Purva Phalguni": ("Rest is not idleness. Enjoy the good things with a thankful heart.", "Bhaga, of good fortune"),
    "Uttara Phalguni": ("Keep your word today. Kept promises make the strongest friendships.", "Aryaman, of friendship"),
    "Hasta": ("Your hands can make anything. Do one small thing with full care.", "Savitar, the Sun"),
    "Chitra": ("Make something beautiful. Good work is a quiet kind of prayer.", "Vishwakarma, the craftsman"),
    "Swati": ("Bend with the wind today. Grass that bends does not break.", "Vayu, the wind"),
    "Vishakha": ("Keep your aim fixed and your patience long. The goal will come.", "Indra and Agni"),
    "Anuradha": ("Be a true friend today. Devotion turns strangers into family.", "Mitra, of friendship"),
    "Jyeshtha": ("Strength is for protecting others. Lead today by looking after people.", "Indra, king of the gods"),
    "Mula": ("Go to the root. Fix the cause, and the problem leaves on its own.", "Nirriti"),
    "Purva Ashadha": ("Like water, keep going. Gentle and steady wins every time.", "Apas, the waters"),
    "Uttara Ashadha": ("Win the right way. A fair victory lasts for ever.", "the Vishvedevas"),
    "Shravana": ("Listen more than you speak today. Wisdom comes through the ears.", "Lord Vishnu"),
    "Dhanishta": ("Share your plenty. Music, food and kindness grow when shared.", "the eight Vasus"),
    "Shatabhisha": ("Healing takes time. Be patient with yourself and with others.", "Varuna, the ocean"),
    "Purva Bhadrapada": ("Burn away one bad habit today. Inner fire makes room for light.", "Aja Ekapada"),
    "Uttara Bhadrapada": ("Still waters run deep. A calm mind sees the answer.", "Ahir Budhnya"),
    "Revati": ("Guide someone home today. Kindness on the road comes back to you.", "Pushan, the guide"),
}


def thought_for(festivals: list[str], tithi: int, nakshatra: str) -> tuple[str, str]:
    """(the thought, where it comes from) for the day."""
    for f in festivals:
        for key, line, src in FESTIVAL:
            if f.startswith(key):
                return line, src
    if tithi in TITHI:
        return TITHI[tithi]
    line, deity = NAKSHATRA[nakshatra]
    return line, f"{nakshatra} Nakshatra · {deity}"
