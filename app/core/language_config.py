"""
Multi-language and multi-state configuration.

Supports expanding the AI Copilot from AP/Telugu to any Indian state and language.
Add a new language by adding an entry to SUPPORTED_LANGUAGES and creating
prompt templates in app/data/prompts/{lang_code}/.
"""

from dataclasses import dataclass, field

# ══════════════════════════════════════════════════════════════
# SUPPORTED LANGUAGES
# ══════════════════════════════════════════════════════════════


@dataclass
class LanguageConfig:
    """Configuration for a supported language."""
    code: str                     # ISO 639-1 (te, hi, kn, ta, etc.)
    name_en: str                  # English name
    name_native: str              # Name in the language itself
    unicode_range: tuple[int, int]  # Unicode block start/end for script detection
    digit_map: str                # Native digits (10 chars: 0-9)
    sentence_delimiters: str      # Characters that end a sentence
    greeting: str                 # "Hello" in this language
    fallback_error: str           # "Service unavailable" message
    busy_error: str               # "Server busy" message
    connection_error: str         # "Internet issue" message
    whisper_prompt: str           # Domain vocabulary for Whisper accuracy
    number_words: dict[str, str]  # Number word -> digit string


SUPPORTED_LANGUAGES: dict[str, LanguageConfig] = {
    "te": LanguageConfig(
        code="te",
        name_en="Telugu",
        name_native="తెలుగు",
        unicode_range=(0x0C00, 0x0C7F),
        digit_map="౦౧౨౩౪౫౬౭౮౯",
        sentence_delimiters="।.!?",
        greeting="నమస్కారం",
        fallback_error="AI సేవ తాత్కాలికంగా అందుబాటులో లేదు. దయచేసి కొద్దిసేపట్లో మళ్ళీ ప్రయత్నించండి.",
        busy_error="సర్వర్ busy గా ఉంది. దయచేసి 1 నిమిషం తర్వాత మళ్ళీ ప్రయత్నించండి.",
        connection_error="Internet connection సమస్య. దయచేసి కొద్దిసేపట్లో మళ్ళీ ప్రయత్నించండి.",
        whisper_prompt=(
            "ఆంధ్రప్రదేశ్ సచివాలయం గ్రామ పథకాలు అమ్మ ఒడి రైతు భరోసా ఆరోగ్యశ్రీ చేయూత "
            "కళ్యాణమస్తు విద్యా దీవెన వసతి దీవెన పెన్షన్ కానుక ఆసరా సున్నా వడ్డీ "
            "దరఖాస్తు అర్హత ప్రయోజనం ఫారం సమర్పించు ఆధార్ రేషన్ కార్డు "
            "మండలం జిల్లా గ్రామం సచివాలయం వలంటీర్ VRO "
            "పేరు వయస్సు ఆదాయం కులం వృత్తి చిరునామా "
            "నమస్కారం దయచేసి ధన్యవాదాలు"
        ),
        number_words={
            "ఒకటి": "1", "రెండు": "2", "మూడు": "3", "నాలుగు": "4", "ఐదు": "5",
            "ఆరు": "6", "ఏడు": "7", "ఎనిమిది": "8", "తొమ్మిది": "9", "పది": "10",
            "ఇరవై": "20", "ముప్పై": "30", "నలభై": "40", "యాభై": "50",
            "అరవై": "60", "డెబ్భై": "70", "ఎనభై": "80", "తొంభై": "90",
            "వంద": "100", "నూరు": "100",
            "వెయ్యి": "1000", "వేయి": "1000",
            "లక్ష": "100000", "లక్షలు": "100000",
            "కోటి": "10000000",
        },
    ),
    "hi": LanguageConfig(
        code="hi",
        name_en="Hindi",
        name_native="हिन्दी",
        unicode_range=(0x0900, 0x097F),
        digit_map="०१२३४५६७८९",
        sentence_delimiters="।.!?",
        greeting="नमस्कार",
        fallback_error="AI सेवा अस्थायी रूप से उपलब्ध नहीं है। कृपया कुछ देर बाद पुनः प्रयास करें।",
        busy_error="सर्वर व्यस्त है। कृपया 1 मिनट बाद पुनः प्रयास करें।",
        connection_error="इंटरनेट कनेक्शन समस्या। कृपया कुछ देर बाद पुनः प्रयास करें।",
        whisper_prompt=(
            "ग्राम सचिवालय पंचायत योजना प्रधानमंत्री किसान सम्मान निधि "
            "आयुष्मान भारत पेंशन राशन कार्ड आधार बैंक खाता "
            "आवेदन पात्रता दस्तावेज़ प्रमाण पत्र "
            "जिला तहसील ग्राम पंचायत सरपंच सचिव "
            "नाम आयु आय जाति व्यवसाय पता "
            "नमस्कार कृपया धन्यवाद"
        ),
        number_words={
            "एक": "1", "दो": "2", "तीन": "3", "चार": "4", "पाँच": "5",
            "छह": "6", "सात": "7", "आठ": "8", "नौ": "9", "दस": "10",
            "बीस": "20", "तीस": "30", "चालीस": "40", "पचास": "50",
            "साठ": "60", "सत्तर": "70", "अस्सी": "80", "नब्बे": "90",
            "सौ": "100", "हज़ार": "1000", "हजार": "1000",
            "लाख": "100000", "करोड़": "10000000",
        },
    ),
    "kn": LanguageConfig(
        code="kn",
        name_en="Kannada",
        name_native="ಕನ್ನಡ",
        unicode_range=(0x0C80, 0x0CFF),
        digit_map="೦೧೨೩೪೫೬೭೮೯",
        sentence_delimiters="।.!?",
        greeting="ನಮಸ್ಕಾರ",
        fallback_error="AI ಸೇವೆ ತಾತ್ಕಾಲಿಕವಾಗಿ ಲಭ್ಯವಿಲ್ಲ. ದಯವಿಟ್ಟು ಸ್ವಲ್ಪ ಸಮಯದ ನಂತರ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
        busy_error="ಸರ್ವರ್ ಬ್ಯುಸಿ ಆಗಿದೆ. ದಯವಿಟ್ಟು 1 ನಿಮಿಷದ ನಂತರ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
        connection_error="ಇಂಟರ್ನೆಟ್ ಸಂಪರ್ಕ ಸಮಸ್ಯೆ. ದಯವಿಟ್ಟು ಸ್ವಲ್ಪ ಸಮಯದ ನಂತರ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
        whisper_prompt=(
            "ಕರ್ನಾಟಕ ಗ್ರಾಮ ಪಂಚಾಯತಿ ಯೋಜನೆ ಪಿಂಚಣಿ ರೇಷನ್ ಕಾರ್ಡ್ ಆಧಾರ್ "
            "ಅರ್ಜಿ ಅರ್ಹತೆ ದಾಖಲೆ ಪ್ರಮಾಣ ಪತ್ರ "
            "ಜಿಲ್ಲೆ ತಾಲೂಕು ಗ್ರಾಮ ಪಂಚಾಯತಿ "
            "ಹೆಸರು ವಯಸ್ಸು ಆದಾಯ ಜಾತಿ ವೃತ್ತಿ ವಿಳಾಸ "
            "ನಮಸ್ಕಾರ ದಯವಿಟ್ಟು ಧನ್ಯವಾದ"
        ),
        number_words={
            "ಒಂದು": "1", "ಎರಡು": "2", "ಮೂರು": "3", "ನಾಲ್ಕು": "4", "ಐದು": "5",
            "ಆರು": "6", "ಏಳು": "7", "ಎಂಟು": "8", "ಒಂಬತ್ತು": "9", "ಹತ್ತು": "10",
            "ಇಪ್ಪತ್ತು": "20", "ಮೂವತ್ತು": "30", "ನಲವತ್ತು": "40", "ಐವತ್ತು": "50",
            "ಅರವತ್ತು": "60", "ಎಪ್ಪತ್ತು": "70", "ಎಂಬತ್ತು": "80", "ತೊಂಬತ್ತು": "90",
            "ನೂರು": "100", "ಸಾವಿರ": "1000",
            "ಲಕ್ಷ": "100000", "ಕೋಟಿ": "10000000",
        },
    ),
    "ta": LanguageConfig(
        code="ta",
        name_en="Tamil",
        name_native="தமிழ்",
        unicode_range=(0x0B80, 0x0BFF),
        digit_map="௦௧௨௩௪௫௬௭௮௯",
        sentence_delimiters="।.!?",
        greeting="வணக்கம்",
        fallback_error="AI சேவை தற்காலிகமாக கிடைக்கவில்லை. சிறிது நேரம் கழித்து மீண்டும் முயற்சிக்கவும்.",
        busy_error="சர்வர் பிஸியாக உள்ளது. 1 நிமிடம் கழித்து மீண்டும் முயற்சிக்கவும்.",
        connection_error="இணைய இணைப்பு சிக்கல். சிறிது நேரம் கழித்து மீண்டும் முயற்சிக்கவும்.",
        whisper_prompt=(
            "தமிழ்நாடு கிராம ஊராட்சி திட்டம் ஓய்வூதியம் ரேஷன் கார்டு ஆதார் "
            "விண்ணப்பம் தகுதி ஆவணம் சான்றிதழ் "
            "மாவட்டம் வட்டம் கிராமம் ஊராட்சி "
            "பெயர் வயது வருமானம் சாதி தொழில் முகவரி "
            "வணக்கம் தயவுசெய்து நன்றி"
        ),
        number_words={
            "ஒன்று": "1", "இரண்டு": "2", "மூன்று": "3", "நான்கு": "4", "ஐந்து": "5",
            "ஆறு": "6", "ஏழு": "7", "எட்டு": "8", "ஒன்பது": "9", "பத்து": "10",
            "இருபது": "20", "முப்பது": "30", "நாற்பது": "40", "ஐம்பது": "50",
            "அறுபது": "60", "எழுபது": "70", "எண்பது": "80", "தொண்ணூறு": "90",
            "நூறு": "100", "ஆயிரம்": "1000",
            "லட்சம்": "100000", "கோடி": "10000000",
        },
    ),
    "mr": LanguageConfig(
        code="mr",
        name_en="Marathi",
        name_native="मराठी",
        unicode_range=(0x0900, 0x097F),  # Shares Devanagari with Hindi
        digit_map="०१२३४५६७८९",
        sentence_delimiters="।.!?",
        greeting="नमस्कार",
        fallback_error="AI सेवा तात्पुरती उपलब्ध नाही. कृपया थोड्या वेळाने पुन्हा प्रयत्न करा.",
        busy_error="सर्व्हर व्यस्त आहे. कृपया 1 मिनिटानंतर पुन्हा प्रयत्न करा.",
        connection_error="इंटरनेट कनेक्शन समस्या. कृपया थोड्या वेळाने पुन्हा प्रयत्न करा.",
        whisper_prompt=(
            "महाराष्ट्र ग्रामपंचायत योजना पेंशन रेशन कार्ड आधार "
            "अर्ज पात्रता कागदपत्रे प्रमाणपत्र "
            "जिल्हा तालुका गाव ग्रामपंचायत सरपंच "
            "नाव वय उत्पन्न जात व्यवसाय पत्ता "
            "नमस्कार कृपया धन्यवाद"
        ),
        number_words={
            "एक": "1", "दोन": "2", "तीन": "3", "चार": "4", "पाच": "5",
            "सहा": "6", "सात": "7", "आठ": "8", "नऊ": "9", "दहा": "10",
            "वीस": "20", "तीस": "30", "चाळीस": "40", "पन्नास": "50",
            "साठ": "60", "सत्तर": "70", "ऐंशी": "80", "नव्वद": "90",
            "शंभर": "100", "हजार": "1000",
            "लाख": "100000", "कोटी": "10000000",
        },
    ),
    "ml": LanguageConfig(
        code="ml",
        name_en="Malayalam",
        name_native="മലയാളം",
        unicode_range=(0x0D00, 0x0D7F),
        digit_map="൦൧൨൩൪൫൬൭൮൯",
        sentence_delimiters="।.!?",
        greeting="നമസ്കാരം",
        fallback_error="AI സേവനം താൽക്കാലികമായി ലഭ്യമല്ല. ദയവായി കുറച്ച് സമയത്തിന് ശേഷം വീണ്ടും ശ്രമിക്കുക.",
        busy_error="സർവർ തിരക്കിലാണ്. ദയവായി 1 മിനിറ്റിന് ശേഷം വീണ്ടും ശ്രമിക്കുക.",
        connection_error="ഇൻ്റർനെറ്റ് കണക്ഷൻ പ്രശ്നം. ദയവായി കുറച്ച് സമയത്തിന് ശേഷം വീണ്ടും ശ്രമിക്കുക.",
        whisper_prompt=(
            "കേരളം ഗ്രാമപഞ്ചായത്ത് പദ്ധതി പെൻഷൻ റേഷൻ കാർഡ് ആധാർ "
            "അപേക്ഷ യോഗ്യത രേഖ സർട്ടിഫിക്കറ്റ് "
            "ജില്ല താലൂക്ക് ഗ്രാമം പഞ്ചായത്ത് "
            "പേര് പ്രായം വരുമാനം ജാതി തൊഴിൽ വിലാസം "
            "നമസ്കാരം ദയവായി നന്ദി"
        ),
        number_words={
            "ഒന്ന്": "1", "രണ്ട്": "2", "മൂന്ന്": "3", "നാല്": "4", "അഞ്ച്": "5",
            "ആറ്": "6", "ഏഴ്": "7", "എട്ട്": "8", "ഒൻപത്": "9", "പത്ത്": "10",
            "ഇരുപത്": "20", "മുപ്പത്": "30", "നാല്പത്": "40", "അൻപത്": "50",
            "അറുപത്": "60", "എഴുപത്": "70", "എൺപത്": "80", "തൊണ്ണൂറ്": "90",
            "നൂറ്": "100", "ആയിരം": "1000",
            "ലക്ഷം": "100000", "കോടി": "10000000",
        },
    ),
    "en": LanguageConfig(
        code="en",
        name_en="English",
        name_native="English",
        unicode_range=(0x0041, 0x007A),
        digit_map="0123456789",
        sentence_delimiters=".!?",
        greeting="Hello",
        fallback_error="AI service is temporarily unavailable. Please try again shortly.",
        busy_error="Server is busy. Please try again in 1 minute.",
        connection_error="Internet connection issue. Please try again shortly.",
        whisper_prompt=(
            "Government secretariat village panchayat scheme pension ration card Aadhaar "
            "application eligibility documents certificate "
            "district mandal village secretariat "
            "name age income caste occupation address"
        ),
        number_words={},  # English numbers handled natively
    ),
}


# ══════════════════════════════════════════════════════════════
# SUPPORTED STATES
# ══════════════════════════════════════════════════════════════


@dataclass
class StateConfig:
    """Configuration for a supported state."""
    code: str                   # State code (AP, TS, KA, TN, etc.)
    name_en: str                # English name
    name_native: str            # Name in state language
    default_language: str       # Primary language code
    supported_languages: list[str]  # All supported languages
    governance_portal_url: str  # State grievance/governance portal
    governance_portal_name: str  # Portal name (GSWS, Meeseva, etc.)
    secretariat_name_en: str    # What they call secretariats
    secretariat_name_native: str
    admin_hierarchy: list[str]  # Escalation levels


SUPPORTED_STATES: dict[str, StateConfig] = {
    "AP": StateConfig(
        code="AP",
        name_en="Andhra Pradesh",
        name_native="ఆంధ్రప్రదేశ్",
        default_language="te",
        supported_languages=["te", "en"],
        governance_portal_url="https://gsws.ap.gov.in/api",
        governance_portal_name="GSWS",
        secretariat_name_en="Sachivalayam",
        secretariat_name_native="సచివాలయం",
        admin_hierarchy=["సచివాలయం", "మండల అధికారి", "జిల్లా కలెక్టర్", "రాష్ట్ర స్థాయి"],
    ),
    "TS": StateConfig(
        code="TS",
        name_en="Telangana",
        name_native="తెలంగాణ",
        default_language="te",
        supported_languages=["te", "en"],
        governance_portal_url="https://panchayat.telangana.gov.in/api",
        governance_portal_name="Panchayat Raj Portal",
        secretariat_name_en="Panchayat Secretary Office",
        secretariat_name_native="పంచాయతీ కార్యదర్శి కార్యాలయం",
        admin_hierarchy=["పంచాయతీ", "మండల అధికారి", "జిల్లా కలెక్టర్", "రాష్ట్ర స్థాయి"],
    ),
    "KA": StateConfig(
        code="KA",
        name_en="Karnataka",
        name_native="ಕರ್ನಾಟಕ",
        default_language="kn",
        supported_languages=["kn", "en"],
        governance_portal_url="https://sevasindhu.karnataka.gov.in/api",
        governance_portal_name="Seva Sindhu",
        secretariat_name_en="Gram Panchayat Office",
        secretariat_name_native="ಗ್ರಾಮ ಪಂಚಾಯತಿ ಕಚೇರಿ",
        admin_hierarchy=["ಗ್ರಾಮ ಪಂಚಾಯತಿ", "ತಾಲೂಕು ಪಂಚಾಯತಿ", "ಜಿಲ್ಲಾ ಪಂಚಾಯತಿ", "ರಾಜ್ಯ ಮಟ್ಟ"],
    ),
    "TN": StateConfig(
        code="TN",
        name_en="Tamil Nadu",
        name_native="தமிழ்நாடு",
        default_language="ta",
        supported_languages=["ta", "en"],
        governance_portal_url="https://tnrd.gov.in/api",
        governance_portal_name="TNRD Portal",
        secretariat_name_en="Village Panchayat Office",
        secretariat_name_native="கிராம ஊராட்சி அலுவலகம்",
        admin_hierarchy=["கிராம ஊராட்சி", "வட்டாட்சியர்", "மாவட்ட ஆட்சியர்", "மாநில அளவு"],
    ),
    "KL": StateConfig(
        code="KL",
        name_en="Kerala",
        name_native="കേരളം",
        default_language="ml",
        supported_languages=["ml", "en"],
        governance_portal_url="https://lsgkerala.gov.in/api",
        governance_portal_name="LSGD Portal",
        secretariat_name_en="Gram Panchayat Office",
        secretariat_name_native="ഗ്രാമപഞ്ചായത്ത് ഓഫീസ്",
        admin_hierarchy=["ഗ്രാമപഞ്ചായത്ത്", "ബ്ലോക്ക് പഞ്ചായത്ത്", "ജില്ലാ കലക്ടർ", "സംസ്ഥാന തലം"],
    ),
    "MH": StateConfig(
        code="MH",
        name_en="Maharashtra",
        name_native="महाराष्ट्र",
        default_language="mr",
        supported_languages=["mr", "hi", "en"],
        governance_portal_url="https://aaplesarkar.mahaonline.gov.in/api",
        governance_portal_name="Aaple Sarkar",
        secretariat_name_en="Gram Panchayat Office",
        secretariat_name_native="ग्रामपंचायत कार्यालय",
        admin_hierarchy=["ग्रामपंचायत", "तहसीलदार", "जिल्हाधिकारी", "राज्य स्तर"],
    ),
    "RJ": StateConfig(
        code="RJ",
        name_en="Rajasthan",
        name_native="राजस्थान",
        default_language="hi",
        supported_languages=["hi", "en"],
        governance_portal_url="https://sampark.rajasthan.gov.in/api",
        governance_portal_name="Sampark Portal",
        secretariat_name_en="Gram Panchayat Office",
        secretariat_name_native="ग्राम पंचायत कार्यालय",
        admin_hierarchy=["ग्राम पंचायत", "तहसीलदार", "जिला कलेक्टर", "राज्य स्तर"],
    ),
    "UP": StateConfig(
        code="UP",
        name_en="Uttar Pradesh",
        name_native="उत्तर प्रदेश",
        default_language="hi",
        supported_languages=["hi", "en"],
        governance_portal_url="https://jansunwai.up.nic.in/api",
        governance_portal_name="Jansunwai Portal",
        secretariat_name_en="Gram Panchayat Office",
        secretariat_name_native="ग्राम पंचायत कार्यालय",
        admin_hierarchy=["ग्राम पंचायत", "तहसीलदार", "जिलाधिकारी", "राज्य स्तर"],
    ),
}

# ══════════════════════════════════════════════════════════════
# LOCALIZED REMINDER TEMPLATES
# ══════════════════════════════════════════════════════════════

REMINDER_TEMPLATES_I18N: dict[str, dict[str, str]] = {
    "te": {
        "pending_documents": (
            "నమస్కారం {citizen_name} గారు, "
            "{scheme_name} పథకం కోసం మీ దరఖాస్తులో కింది పత్రాలు పెండింగ్‌లో ఉన్నాయి: "
            "{documents}. "
            "దయచేసి {deadline} లోపు మీ సచివాలయానికి తీసుకురండి."
        ),
        "renewal_deadline": (
            "నమస్కారం {citizen_name} గారు, "
            "{scheme_name} పథకం రెన్యూవల్ గడువు {deadline} న ముగుస్తుంది. "
            "దయచేసి సమయానికి మీ సచివాలయంలో రెన్యూవల్ చేయించుకోండి."
        ),
        "disbursement_date": (
            "నమస్కారం {citizen_name} గారు, "
            "{scheme_name} పథకం ద్వారా మీ ఖాతాలో {date} న నగదు జమ అవుతుంది. "
            "మీ బ్యాంక్ ఖాతా వివరాలు సరిగ్గా ఉన్నాయో ధృవీకరించుకోండి."
        ),
        "application_followup": (
            "నమస్కారం {citizen_name} గారు, "
            "{scheme_name} పథకం దరఖాస్తు స్థితి: ప్రాసెస్‌లో ఉంది. "
            "ఏదైనా అదనపు సమాచారం అవసరమైతే మీ సచివాలయాన్ని సంప్రదించండి."
        ),
    },
    "hi": {
        "pending_documents": (
            "नमस्कार {citizen_name} जी, "
            "{scheme_name} योजना के लिए आपके आवेदन में निम्नलिखित दस्तावेज़ लंबित हैं: "
            "{documents}. "
            "कृपया {deadline} तक अपने सचिवालय में जमा करें।"
        ),
        "renewal_deadline": (
            "नमस्कार {citizen_name} जी, "
            "{scheme_name} योजना का नवीनीकरण {deadline} को समाप्त हो रहा है। "
            "कृपया समय पर अपने सचिवालय में नवीनीकरण करवाएं।"
        ),
        "disbursement_date": (
            "नमस्कार {citizen_name} जी, "
            "{scheme_name} योजना के तहत आपके खाते में {date} को राशि जमा होगी। "
            "कृपया अपने बैंक खाते का विवरण सही है, इसकी पुष्टि करें।"
        ),
        "application_followup": (
            "नमस्कार {citizen_name} जी, "
            "{scheme_name} योजना आवेदन की स्थिति: प्रक्रिया में है। "
            "किसी भी अतिरिक्त जानकारी के लिए अपने सचिवालय से संपर्क करें।"
        ),
    },
    "kn": {
        "pending_documents": (
            "ನಮಸ್ಕಾರ {citizen_name} ಅವರೇ, "
            "{scheme_name} ಯೋಜನೆಗೆ ನಿಮ್ಮ ಅರ್ಜಿಯಲ್ಲಿ ಈ ಕೆಳಗಿನ ದಾಖಲೆಗಳು ಬಾಕಿ ಇವೆ: "
            "{documents}. "
            "ದಯವಿಟ್ಟು {deadline} ಒಳಗೆ ನಿಮ್ಮ ಗ್ರಾಮ ಪಂಚಾಯತಿಗೆ ತಂದುಕೊಡಿ."
        ),
        "renewal_deadline": (
            "ನಮಸ್ಕಾರ {citizen_name} ಅವರೇ, "
            "{scheme_name} ಯೋಜನೆ ನವೀಕರಣ ಗಡುವು {deadline} ರಂದು ಮುಗಿಯುತ್ತದೆ. "
            "ದಯವಿಟ್ಟು ಸಮಯಕ್ಕೆ ಸರಿಯಾಗಿ ನವೀಕರಿಸಿ."
        ),
        "disbursement_date": (
            "ನಮಸ್ಕಾರ {citizen_name} ಅವರೇ, "
            "{scheme_name} ಯೋಜನೆಯ ಮೂಲಕ ನಿಮ್ಮ ಖಾತೆಗೆ {date} ರಂದು ಹಣ ಜಮೆಯಾಗುತ್ತದೆ. "
            "ನಿಮ್ಮ ಬ್ಯಾಂಕ್ ಖಾತೆ ವಿವರಗಳನ್ನು ಪರಿಶೀಲಿಸಿ."
        ),
        "application_followup": (
            "ನಮಸ್ಕಾರ {citizen_name} ಅವರೇ, "
            "{scheme_name} ಯೋಜನೆ ಅರ್ಜಿ ಸ್ಥಿತಿ: ಪ್ರಕ್ರಿಯೆಯಲ್ಲಿದೆ. "
            "ಯಾವುದೇ ಹೆಚ್ಚುವರಿ ಮಾಹಿತಿಗಾಗಿ ನಿಮ್ಮ ಗ್ರಾಮ ಪಂಚಾಯತಿಯನ್ನು ಸಂಪರ್ಕಿಸಿ."
        ),
    },
    "en": {
        "pending_documents": (
            "Dear {citizen_name}, "
            "the following documents are pending for your {scheme_name} application: "
            "{documents}. "
            "Please submit them at your local office by {deadline}."
        ),
        "renewal_deadline": (
            "Dear {citizen_name}, "
            "your {scheme_name} renewal deadline is {deadline}. "
            "Please renew at your local office in time."
        ),
        "disbursement_date": (
            "Dear {citizen_name}, "
            "your {scheme_name} payment will be credited to your account on {date}. "
            "Please verify your bank account details are correct."
        ),
        "application_followup": (
            "Dear {citizen_name}, "
            "your {scheme_name} application status: in process. "
            "Contact your local office for any additional information."
        ),
    },
}

# ══════════════════════════════════════════════════════════════
# LOCALIZED DOCUMENT NAMES
# ══════════════════════════════════════════════════════════════

# key -> (te, hi, kn, ta, en)
COMMON_DOCUMENTS_I18N: dict[str, dict[str, str]] = {
    "aadhaar_card": {"te": "ఆధార్ కార్డు", "hi": "आधार कार्ड", "kn": "ಆಧಾರ್ ಕಾರ್ಡ್", "ta": "ஆதார் அட்டை", "en": "Aadhaar Card"},
    "ration_card": {"te": "రేషన్ కార్డు", "hi": "राशन कार्ड", "kn": "ರೇಷನ್ ಕಾರ್ಡ್", "ta": "ரேஷன் கார்டு", "en": "Ration Card"},
    "income_certificate": {"te": "ఆదాయ ధృవీకరణ పత్రం", "hi": "आय प्रमाण पत्र", "kn": "ಆದಾಯ ಪ್ರಮಾಣ ಪತ್ರ", "ta": "வருமானச் சான்றிதழ்", "en": "Income Certificate"},
    "caste_certificate": {"te": "కులధృవీకరణ పత్రం", "hi": "जाति प्रमाण पत्र", "kn": "ಜಾತಿ ಪ್ರಮಾಣ ಪತ್ರ", "ta": "சாதிச் சான்றிதழ்", "en": "Caste Certificate"},
    "residence_certificate": {"te": "నివాస ధృవీకరణ పత్రం", "hi": "निवास प्रमाण पत्र", "kn": "ನಿವಾಸ ಪ್ರಮಾಣ ಪತ್ರ", "ta": "வசிப்பிடச் சான்றிதழ்", "en": "Residence Certificate"},
    "bank_passbook": {"te": "బ్యాంకు పాస్‌బుక్", "hi": "बैंक पासबुक", "kn": "ಬ್ಯಾಂಕ್ ಪಾಸ್‌ಬುಕ್", "ta": "வங்கி பாஸ்புக்", "en": "Bank Passbook"},
    "passport_photo": {"te": "పాస్‌పోర్ట్ సైజు ఫోటో", "hi": "पासपोर्ट साइज़ फोटो", "kn": "ಪಾಸ್‌ಪೋರ್ಟ್ ಫೋಟೋ", "ta": "பாஸ்போர்ட் புகைப்படம்", "en": "Passport Photo"},
    "voter_id": {"te": "ఓటరు గుర్తింపు కార్డు", "hi": "मतदाता पहचान पत्र", "kn": "ಮತದಾರರ ಗುರುತಿನ ಚೀಟಿ", "ta": "வாக்காளர் அடையாள அட்டை", "en": "Voter ID"},
    "birth_certificate": {"te": "జనన ధృవీకరణ పత్రం", "hi": "जन्म प्रमाण पत्र", "kn": "ಜನನ ಪ್ರಮಾಣ ಪತ್ರ", "ta": "பிறப்புச் சான்றிதழ்", "en": "Birth Certificate"},
    "disability_certificate": {"te": "వికలాంగ ధృవీకరణ పత్రం", "hi": "विकलांगता प्रमाण पत्र", "kn": "ಅಂಗವಿಕಲತೆ ಪ್ರಮಾಣ ಪತ್ರ", "ta": "ஊனமுற்றோர் சான்றிதழ்", "en": "Disability Certificate"},
    "land_document": {"te": "భూమి పత్రాలు / పట్టాదారు పాస్‌బుక్", "hi": "भूमि दस्तावेज़ / खतौनी", "kn": "ಭೂ ದಾಖಲೆ / ಪಹಣಿ", "ta": "நில ஆவணம் / பட்டா", "en": "Land Document / Pattadar Passbook"},
    "school_certificate": {"te": "పాఠశాల ధృవీకరణ పత్రం", "hi": "विद्यालय प्रमाण पत्र", "kn": "ಶಾಲಾ ಪ್ರಮಾಣ ಪತ್ರ", "ta": "பள்ளிச் சான்றிதழ்", "en": "School Certificate"},
    "death_certificate": {"te": "మరణ ధృవీకరణ పత్రం", "hi": "मृत्यु प्रमाण पत्र", "kn": "ಮರಣ ಪ್ರಮಾಣ ಪತ್ರ", "ta": "இறப்புச் சான்றிதழ்", "en": "Death Certificate"},
    "marriage_certificate": {"te": "వివాహ ధృవీకరణ పత్రం", "hi": "विवाह प्रमाण पत्र", "kn": "ವಿವಾಹ ಪ್ರಮಾಣ ಪತ್ರ", "ta": "திருமணச் சான்றிதழ்", "en": "Marriage Certificate"},
    "medical_certificate": {"te": "వైద్య ధృవీకరణ పత్రం", "hi": "चिकित्सा प्रमाण पत्र", "kn": "ವೈದ್ಯಕೀಯ ಪ್ರಮಾಣ ಪತ್ರ", "ta": "மருத்துவச் சான்றிதழ்", "en": "Medical Certificate"},
}


# ══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════


def get_language_config(lang_code: str) -> LanguageConfig:
    """Get config for a language. Falls back to English if unsupported."""
    return SUPPORTED_LANGUAGES.get(lang_code, SUPPORTED_LANGUAGES["en"])


def get_state_config(state_code: str) -> StateConfig:
    """Get config for a state. Falls back to AP if unsupported."""
    return SUPPORTED_STATES.get(state_code, SUPPORTED_STATES["AP"])


def get_reminder_template(lang_code: str, template_type: str) -> str:
    """Get a localized reminder template. Falls back to English."""
    templates = REMINDER_TEMPLATES_I18N.get(lang_code, REMINDER_TEMPLATES_I18N["en"])
    return templates.get(template_type, REMINDER_TEMPLATES_I18N["en"].get(template_type, ""))


def get_document_name(doc_key: str, lang_code: str) -> str:
    """Get localized document name. Falls back to English."""
    doc = COMMON_DOCUMENTS_I18N.get(doc_key, {})
    return doc.get(lang_code, doc.get("en", doc_key))


def detect_language_from_text(text: str) -> str:
    """Detect language from text using Unicode script ranges."""
    import re
    best_lang = "en"
    best_count = 0

    for lang_code, config in SUPPORTED_LANGUAGES.items():
        if lang_code == "en":
            continue
        start, end = config.unicode_range
        pattern = f"[\\u{start:04X}-\\u{end:04X}]"
        count = len(re.findall(pattern, text))
        if count > best_count:
            best_count = count
            best_lang = lang_code

    # If no native script detected, check if it's English
    if best_count == 0:
        return "en"

    # Require at least 15% native script to classify
    total_alpha = len(re.findall(r"[a-zA-Z]", text)) + best_count
    if total_alpha > 0 and best_count / total_alpha > 0.15:
        return best_lang

    return "en"


def list_supported_languages() -> list[dict]:
    """Return list of supported languages for API response."""
    return [
        {
            "code": cfg.code,
            "name_en": cfg.name_en,
            "name_native": cfg.name_native,
        }
        for cfg in SUPPORTED_LANGUAGES.values()
    ]


def list_supported_states() -> list[dict]:
    """Return list of supported states for API response."""
    return [
        {
            "code": cfg.code,
            "name_en": cfg.name_en,
            "name_native": cfg.name_native,
            "default_language": cfg.default_language,
            "supported_languages": cfg.supported_languages,
        }
        for cfg in SUPPORTED_STATES.values()
    ]
