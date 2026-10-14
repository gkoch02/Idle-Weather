"""The phrases the miner looks for, per weather condition, and the figures of speech it skips.

Each condition has a list of patterns that name the weather itself ("the rain
was falling", "a hard frost"), not a bare keyword: "rain" alone would also
find "a rain of blows" and "Lorraine". The match is what the panel shows in
bold, so a pattern takes in the verb or adjective that makes it weather.

``NEGATIVE`` lists figurative or non-weather uses, checked against a window
around the match; a hit there drops the candidate. Stdlib only.
"""
from __future__ import annotations

import re


def _alt(*words: str) -> str:
    return "(?:" + "|".join(words) + ")"


_ART = r"(?:(?:the|a|an|this|that|such\s+a)\s+)?"

# Weather adjectives that may stand before a noun ("a cold rain").
_RAIN_ADJ = _alt(
    "cold", "chill", "chilly", "warm", "soft", "gentle", "steady", "grey", "gray", "dreary", "ceaseless",
    "incessant", "persistent", "summer", "autumn", "winter", "spring", "april", "november", "october",
    "night", "morning", "heavy", "driving", "pelting", "pouring", "drenching", "lashing", "beating",
    "falling", "fine", "thin", "light", "small", "slanting", "dismal", "endless", "continual", "icy",
)

PATTERNS: dict[str, list[str]] = {
    "thunder": [
        r"\bthunder[- ]?storms?\b",
        r"\b(?:a\s+|the\s+)?(?:distant\s+|low\s+|deep\s+|loud\s+|sudden\s+)?(?:peals?|claps?|rolls?|crash(?:es)?|growl|mutterings?|rumbl(?:e|ing))\s+of\s+thunder\b",
        r"\bthunder[- ]?claps?\b",
        r"\b(?:the\s+)?thunder\s+(?:rolled|rumbled|growled|crashed|pealed|muttered|roared|broke|burst|boomed|crackled|sounded)\b",
        r"\b(?:the\s+)?(?:distant\s+|far-off\s+|low\s+)?thunder\s+(?:was|had\s+been)\s+(?:rolling|rumbling|growling|muttering|crashing)\b",
        r"\b(?:it|there)\s+(?:was\s+|had\s+been\s+|began\s+to\s+)?thunder(?:ed|ing)?\b",
        r"\b(?:a\s+|the\s+)?(?:vivid\s+|sudden\s+|blinding\s+|livid\s+|white\s+|forked\s+|sheet\s+)?flash(?:es)?\s+of\s+(?:forked\s+|sheet\s+)?lightning\b",
        r"\bthe\s+lightning\s+(?:flashed|played|gleamed|glared|lit|lighted|struck|blazed|split|zigzagged|was\s+(?:flashing|playing))\b",
        r"\bthunder\s+and\s+lightning\b",
        r"\blightning\s+and\s+thunder\b",
    ],
    "snow": [
        r"\b(?:the\s+)?snow\s+(?:was\s+|had\s+been\s+|is\s+)?(?:falling|fell|drifted|drifting|lay|lies|was\s+lying|had\s+fallen|came\s+down|whirled|whirling|swirled|swirling|covered|blew|blowing)\b",
        r"\b(?:it|the\s+sky)\s+(?:was\s+|had\s+been\s+|began\s+to\s+|had\s+begun\s+to\s+|continued\s+to\s+|is\s+|kept\s+on\s+)?snow(?:ed|ing)?\b(?!\s*-?white)",
        r"\bsnow[- ]?(?:flakes?|storms?|falls?|drifts?)\b",
        r"\b(?:the\s+)?(?:falling|driving|whirling|deep|fresh|new|thick|soft|powdery|drifting|blinding|first)\s+snow\b",
        r"\bblizzards?\b",
        r"~\b(?:covered|white|deep|thick|buried|heavy)\s+with\s+snow\b",
        r"\bflakes\s+of\s+snow\b",
    ],
    "sleet": [
        r"\bsleet(?:ing|y)?\b",
        r"\bhail[- ]?stones?\b",
        r"\bhail[- ]?storms?\b",
        r"\b(?:a\s+)?(?:storm|shower|fall)\s+of\s+hail\b",
        r"\bthe\s+hail\s+(?:fell|beat|rattled|came|was\s+falling|pelted|lashed|drove)\b",
        r"\bfreezing\s+rain\b",
        r"\bsnow\s+and\s+rain\b",
        r"\brain\s+and\s+snow\b",
    ],
    "downpour": [
        r"\bdown[- ]?pours?\b",
        r"\b(?:the\s+|a\s+)?(?:pouring|heavy|torrential|drenching|pelting|driving|lashing|tropical|violent)\s+rain\b",
        r"\btorrents?\s+of\s+rain\b",
        r"\brain\s+(?:fell|came\s+down|poured(?:\s+down)?|was\s+(?:falling|pouring|coming\s+down))\s+in\s+(?:torrents|sheets|buckets|floods|streams)\b",
        r"\b(?:the\s+)?rain\s+(?:poured|was\s+pouring|pelted|was\s+pelting|lashed|drove|beat|was\s+beating|streamed|teemed)\b",
        r"\b(?:it|the\s+sky)\s+(?:was\s+|had\s+been\s+|began\s+to\s+)?pour(?:ed|ing)\s+(?:with\s+rain|down)\b",
        r"\bpouring\s+with\s+rain\b",
        r"\bdeluge\s+of\s+rain\b",
        r"\braining\s+(?:hard|heavily|in\s+torrents|cats\s+and\s+dogs)\b",
    ],
    "rain": [
        r"\b(?:it|the\s+sky)\s+(?:was\s+|had\s+been\s+|began\s+to\s+|had\s+begun\s+to\s+|continued\s+to\s+|is\s+|kept\s+on\s+|still\s+)?rain(?:ed|ing)\b",
        r"\b(?:the\s+)?rain\s+(?:was\s+|had\s+been\s+|is\s+)?(?:falling|fell|pattered|pattering|dripped|dripping|came\s+on|came\s+down|had\s+ceased|ceased|stopped|had\s+stopped|began|had\s+begun|beat\s+upon|beat\s+against|rattled|splashed|streamed\s+down|ran\s+down|trickled|tapped|whispered|set\s+in|held\s+off|kept\s+on)\b",
        r"\b(?:a|the)\s+" + _RAIN_ADJ + r"\s+rain\b",
        r"\b(?:showers?|drops?|patter|pattering|sound|noise|splash)\s+of\s+(?:the\s+)?rain\b",
        r"\brain[- ]?drops?\b",
        r"\brainy\s+(?:day|night|morning|evening|afternoon|weather|season)s?\b",
        r"~\bwet\s+(?:day|night|morning|evening|afternoon|weather)\b",
        r"~\bin\s+the\s+rain\b",
        r"~\bout\s+of\s+the\s+rain\b",
        r"~\bthe\s+rain\b(?=[.,;:!?])",
    ],
    "drizzle": [
        r"\bdrizzl(?:e|ed|ing|y)\b",
        r"\b(?:a|the)\s+(?:fine|small|thin|light|misty|soft|gentle|cold|grey|gray)\s+(?:drizzling\s+)?rain\b",
        r"\bscotch\s+mist\b",
        r"\bspitting\s+(?:with\s+)?rain\b",
        r"\bmizzl(?:e|ing)\b",
    ],
    "fog": [
        r"~\b(?:the\s+|a\s+)?(?:thick\s+|dense\s+|heavy\s+|white\s+|grey\s+|gray\s+|yellow\s+|brown\s+|damp\s+|cold\s+|london\s+|sea\s+|river\s+|morning\s+|evening\s+|night\s+)?fogs?\b(?!\s+of\s+(?:his|her|their|my|the)\s+(?:mind|brain|thought))",
        r"~\bfoggy\b",
        r"\b(?:the\s+|a\s+)?(?:thick\s+|dense\s+|heavy\s+|white\s+|grey\s+|gray\s+|damp\s+|cold\s+|morning\s+|evening\s+|thin\s+|blue\s+|river\s+|sea\s+|rising\s+)?mists?\s+(?:rose|was\s+rising|hung|lay|was\s+lying|crept|drifted|clung|rolled|came\s+up|had\s+risen|lifted|was\s+lifting|cleared|covered|veiled|shrouded|wrapped|filled|hid|over\s+the|on\s+the|from\s+the)\b",
        r"\bmisty\s+(?:morning|evening|night|day|air|weather|rain|valley|hills?|fields?|meadows?|river|sea|moon|light)\b",
        r"\b(?:the\s+)?(?:morning|evening|white|river|sea)\s+mists?\b",
        r"\bfog-?bank\b",
    ],
    "wind": [
        r"\b(?:the\s+)?(?:north|south|east|west|north-east|north-west|south-east|south-west|northeast|northwest|southeast|southwest|bitter|cold|icy|keen|raw|biting|fierce|wild|furious|violent|strong|high|howling|roaring|rising|boisterous)?\s*wind\s+(?:was\s+|had\s+been\s+)?(?:blew|blowing|howled|howling|roared|roaring|moaned|moaning|whistled|whistling|shrieked|shrieking|wailed|wailing|raged|raging|rose|had\s+risen|was\s+rising|tore|swept|sweeping|rattled|rattling|buffeted|lashed|shook|beat|battered|sighed|sighing|soughed|sobbed|screamed|screaming|piped|bellowed|gusted)\b",
        r"\b(?:the\s+)?wind\s+(?:was|had\s+been)\s+(?:high|strong|rising|bitter|cold|keen|raw|fierce|wild|boisterous|blowing\s+hard|very\s+high|still\s+high)\b",
        r"~\b(?:a\s+|the\s+)?(?:whole\s+|stiff\s+|strong\s+|fierce\s+|furious\s+|violent\s+|howling\s+|terrible\s+|heavy\s+|rising\s+|northerly\s+|southerly\s+|easterly\s+|westerly\s+)?gales?\b(?!\s+of\s+(?:laughter|merriment|mirth))",
        r"\b(?:a|the)\s+(?:high|strong|fierce|wild|violent|howling|roaring|furious|biting|bitter|piercing|boisterous|blustering|gusty)\s+wind\b",
        r"\bgusts?\s+of\s+wind\b",
        r"\b(?:windy|blustery|blustering|gusty|stormy)\s+(?:day|night|morning|evening|afternoon|weather|sky|sea|march)\b",
        r"\b(?:it|the\s+wind)\s+(?:was\s+|had\s+been\s+)?blowing\s+(?:hard|a\s+gale|great\s+guns|fiercely|furiously|half\s+a\s+gale)\b",
        r"\bwhistling\s+of\s+the\s+wind\b",
        r"\bhowling\s+of\s+the\s+wind\b",
    ],
    "clouds": [
        r"\bovercast\b",
        r"\b(?:the\s+)?sky\s+(?:was|had\s+become|had\s+grown|grew|is)\s+(?:grey|gray|overcast|clouded|cloudy|dull|leaden|dark|heavy|lowering|threatening|murky|sullen)\b",
        r"\b(?:a|the)\s+(?:grey|gray|leaden|lowering|clouded|cloudy|dull|sullen|heavy|overcast)\s+sky\b",
        r"\bcloudy\s+(?:day|morning|evening|afternoon|weather|sky|night)\b",
        r"\b(?:heavy|dark|grey|gray|low|black|leaden|scudding|thick|lowering|massed|rain|storm|ragged|great|white|fleecy|drifting)\s+clouds\s+(?:hung|covered|scudded|drifted|rolled|raced|gathered|were\s+gathering|hid|obscured|filled|swept|massed|moved|lay|sailed|floated|passed|darkened)\b",
        r"\bthe\s+clouds\s+(?:hung|covered|scudded|drifted|rolled|raced|gathered|were\s+gathering|hid|obscured|filled|swept|massed|lay|sailed|floated|darkened|lowered|broke|parted|thickened)\b",
        r"\b(?:a\s+)?(?:grey|gray|dull|cloudy|sunless|overcast|murky|raw)\s+(?:day|morning|afternoon)\b",
        r"\b(?:sky|heavens|it|weather|day|morning|afternoon)\s+(?:had\s+)?clouded\s+over\b",
    ],
    "sunshine": [
        r"~\b(?:the\s+)?(?:bright\s+|warm\s+|brilliant\s+|glorious\s+|golden\s+|morning\s+|afternoon\s+|spring\s+|summer\s+|autumn\s+|winter\s+|pale\s+|soft\s+)?sunshine\b(?!\s+of\s+(?:his|her|their|your|my)\b)",
        r"\bthe\s+sun\s+(?:was\s+|had\s+been\s+)?(?:shone|shining|blazed|blazing|beat\s+down|beating\s+down|came\s+out|had\s+come\s+out|broke\s+through|burst\s+through|streamed|was\s+bright|was\s+warm|was\s+brilliant|glittered|sparkled|poured)\b",
        r"\bsunny\s+(?:day|morning|afternoon|weather|sky|hours|spring|summer)\b",
        r"\b(?:a|the)\s+(?:cloudless|blue|clear|bright)\s+sky\b",
        r"\b(?:a|the)\s+(?:fine|bright|glorious|beautiful|lovely|clear|brilliant|perfect|radiant|cloudless|sunny)\s+(?:day|morning|afternoon)\b",
        r"~\bblue\s+skies?\b",
        r"\bsunlight\s+(?:streamed|poured|fell|lay|flooded|filled|glinted|sparkled|danced|shone|was\s+streaming)\b",
    ],
    "heat": [
        r"\bthe\s+heat\s+(?:was|had\s+been|grew|became|of\s+the\s+(?:day|sun|afternoon|noon|summer|weather))\b",
        r"\b(?:sultry|scorching|sweltering|stifling|oppressive|blazing|burning|fierce|intense|great|terrific|tropical|noonday|midday)\s+heat\b",
        r"\b(?:a\s+|the\s+)?(?:sultry|scorching|sweltering|stifling|oppressive|broiling|baking|blazing|burning|hot)\s+(?:day|afternoon|weather|morning|noon|summer|sun)\b",
        r"\b(?:the\s+)?(?:day|afternoon|weather|air|morning|noon)\s+(?:was|had\s+been|grew|had\s+grown|became)\s+(?:very\s+|intensely\s+|insufferably\s+|oppressively\s+)?(?:hot|sultry|close|stifling|sweltering|scorching|oppressive)\b",
        r"\bheat[- ]?waves?\b",
        r"\bdog[- ]days\b",
        r"\b(?:it|the\s+sun)\s+was\s+(?:very\s+|intensely\s+|terribly\s+|insufferably\s+)?(?:hot|scorching|blazing)\b",
    ],
    "frost": [
        r"\b(?:a\s+|the\s+)?(?:hard|sharp|severe|keen|white|black|bitter|heavy|early|first|morning|night|killing)\s+frosts?\b",
        r"\bthe\s+frost\s+(?:was|had|lay|glittered|sparkled|bit|nipped|covered|silvered|whitened|held)\b",
        r"\bhoar[- ]?frost\b",
        r"\bfrosty\s+(?:morning|night|air|weather|evening|day|sky|ground|grass|starlight|stars|moonlight|road|fields?)\b",
        r"\b(?:it|the\s+(?:air|day|night|morning|evening|weather))\s+(?:was|had\s+been|grew|had\s+grown|became)\s+(?:bitterly|intensely|piercingly|freezing|bitter|very|terribly|so|extremely)\s+cold\b",
        r"\b(?:bitter|biting|intense|piercing|freezing|severe)\s+cold\b",
        r"\bfreezing\s+(?:weather|air|wind|night|morning|cold)\b",
        r"~\bicicles?\b",
        r"\b(?:the\s+)?(?:pond|lake|river|ground|earth|road|streams?|canal|water)\s+(?:was|were|had\s+been|lay)\s+(?:frozen|hard\s+frozen|frozen\s+hard)\b",
    ],
    "night_sky": [
        r"~\b(?:the\s+)?(?:bright\s+|pale\s+|white\s+|silver\s+|silvery\s+|cold\s+|clear\s+|full\s+)?moonlight\b",
        r"~\bmoon-?lit\b",
        r"\bthe\s+moon\s+(?:was\s+|had\s+been\s+)?(?:shone|shining|rose|risen|had\s+risen|was\s+up|was\s+full|sailed|sailing|came\s+out|hung|rode|riding|silvered|flooded|poured|was\s+bright|was\s+high)\b",
        r"\bthe\s+(?:full|harvest|rising|new|crescent|young|round|bright|white|pale)\s+moon\b",
        r"~\bstar-?light\b",
        r"~\bstar-?lit\b",
        r"\bstarry\s+(?:sky|night|heavens?|vault|dome)\b",
        r"\bthe\s+stars\s+(?:were\s+|had\s+been\s+)?(?:shone|shining|came\s+out|had\s+come\s+out|twinkled|twinkling|glittered|glittering|sparkled|sparkling|were\s+out|burned|blazed|gleamed|glimmered|appeared)\b",
        r"\b(?:a|the)\s+(?:clear|cloudless|still|calm)\s+(?:starry\s+|moonlit\s+)?night\b",
    ],
}

# Figurative or non-weather uses, checked against ±40 characters around the
# match. Any hit drops the candidate.
NEGATIVE: dict[str, list[str]] = {
    "*": [
        r"\b(?:like|as)\s+(?:a\s+|the\s+)?(?:thunder|lightning|snow|rain|hail|a\s+storm|frost|fog|mist|the\s+wind|wind)\b(?![-\s]?(?:fell|was|had|storm))",
        r"\b(?:white|pure|cold|soft)\s+as\s+(?:the\s+)?snow\b",
        r"\bsnow[- ]?(?:white|drops?|balls?|man|men|shoes?)\b",
        r"\b(?:rain|shower|storm|hail|torrent|deluge|cloud)s?\s+of\s+(?:blows|arrows|bullets|shot|stones|missiles|tears|kisses|sparks|words|questions|abuse|curses|gold|ashes|applause|invective|reproaches|insults|compliments|flowers|petals|confetti|dust|smoke|steam|witnesses|flies|insects|locusts|spray|sand|eloquence)\b",
        r"\b(?:fog|mist|cloud|clouds)\s+(?:of|over|before|across|in)\s+(?:his|her|my|their|your)\s+(?:mind|brain|eyes|vision|memory|thoughts|brow|face|senses)\b",
        r"\b(?:his|her|my|their|your)\s+(?:eyes|brain|mind|vision)\s+(?:was|were|grew|became)\s+(?:misty|clouded|foggy)\b",
        r"\btears\b",
        r"\bunder\s+a\s+cloud\b",
        r"\bthunder(?:struck|-struck|bolt|ous)\b",
        r"\b(?:steal|stole|stolen)\s+(?:his|my|their|her)\s+thunder\b",
        r"\bthunder\s+of\s+(?:the\s+)?(?:guns?|cannons?|artillery|hoofs|hooves|applause|the\s+surf|the\s+waves|the\s+sea|the\s+falls|the\s+cataract|wheels|drums|the\s+organ|voices|feet)\b",
        r"\b(?:lightning|lightening)\s+(?:speed|rapidity|quickness|swiftness|calculator)\b",
        r"\bwith\s+(?:the\s+)?(?:speed|rapidity|swiftness|quickness)\s+of\s+lightning\b",
        r"\bheat\s+of\s+(?:passion|anger|the\s+moment|the\s+argument|battle|the\s+battle|the\s+debate|the\s+chase|the\s+fight|controversy|discussion|youth|his|her)\b",
        r"\b(?:got|get|gets|getting|caught)\s+wind\s+of\b",
        r"\bsecond\s+wind\b",
        r"\bwind\s+(?:instruments?|of\s+(?:rumou?r|change|doctrine))\b",
        r"\bsunshine\s+of\s+(?:his|her|their|your|my|a)\b",
        r"\b(?:my|our|his|her)\s+(?:little\s+)?sunshine\b",
        r"\bfrosty\s+(?:manner|smile|look|reception|politeness|tone|glance|bow|voice|answer|stare)\b",
        r"\bstars?\s+(?:in|of)\s+(?:his|her|their|your|my)\s+eyes\b",
        r"\b(?:film|movie|stage|theatre|theater)\b",
        r"\bmetaphor|simile|figuratively\b",
        r"\b(?:like|as\s+if|as\s+though|as\s+by)\s+(?:a\s+)?(?:\w+\s+)?(?:flash|clap|peal|bolt|thunderclap)\b",
        r"\b(?:fog|mist|haze|wind|winds|storm|cloud|clouds|sunshine)\s+of\s+(?:its|his|her|their|my|our|your)\b",
        r"\b(?:brow|face|countenance|eyes|forehead|features|expression)\s+(?:had\s+)?(?:clouded|darkened)\b",
        r"\blike\s+(?:a\s+|the\s+)?(?:hailstones|hail|snowflakes|raindrops|fog|mist|smoke)\b",
    ],
}

# Words that suggest the sentence is about the weather outside, used as a
# small score bonus.
WEATHER_CONTEXT = (
    "sky", "skies", "window", "windows", "roof", "roofs", "street", "streets", "outside", "out of doors",
    "garden", "fields", "hills", "trees", "leaves", "road", "morning", "evening", "night", "afternoon",
    "weather", "clouds", "air", "umbrella", "cloak", "coat", "shelter", "pane", "panes", "sea", "river",
    "moor", "lane", "wet", "drenched", "soaked", "shivered", "season", "winter", "summer", "autumn", "spring",
)


# Words of weather itself. An excerpt that names more of them than its matched
# phrase is about the weather, not passing through it.
WEATHER_LEXICON = (
    "rain", "rained", "raining", "rains", "drops", "wind", "winds", "breeze", "gale", "gust", "gusts", "snow",
    "snowing", "flakes", "sky", "skies", "cloud", "clouds", "fog", "mist", "haze", "sun", "sunshine", "sunlight",
    "storm", "thunder", "lightning", "frost", "frozen", "ice", "cold", "chill", "hail", "sleet", "drizzle",
    "moon", "moonlight", "stars", "starlight", "heat", "hot", "sultry", "weather", "wet", "dripping",
    "puddles", "dew", "damp", "shower", "showers", "blew", "blowing", "howled", "shone", "shining",
)

# A leading "~" marks a weak pattern: a bare noun ("the fog", "moonlight") that
# finds weather mentioned in passing as often as weather described.
WEAK_PREFIX = "~"


def compile_patterns() -> dict[str, list[tuple[re.Pattern[str], bool]]]:
    """Each condition's patterns as ``(compiled, weak)`` pairs."""
    return {
        cond: [(re.compile(p.removeprefix(WEAK_PREFIX), re.IGNORECASE), p.startswith(WEAK_PREFIX)) for p in pats]
        for cond, pats in PATTERNS.items()
    }


def compile_negative() -> list[re.Pattern[str]]:
    return [re.compile(p, re.IGNORECASE) for p in NEGATIVE["*"]]
