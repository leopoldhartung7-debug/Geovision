"""Label data for zero-shot geolocation and visual signal analysis.

Country list is curated (not exhaustive) to keep inference fast. StreetCLIP was
trained on country-level prompts, so these prompts match its training distribution.
"""

# (country, continent)
COUNTRIES: list[tuple[str, str]] = [
    ("Germany", "Europe"), ("France", "Europe"), ("Italy", "Europe"), ("Spain", "Europe"),
    ("Portugal", "Europe"), ("United Kingdom", "Europe"), ("Ireland", "Europe"),
    ("Netherlands", "Europe"), ("Belgium", "Europe"), ("Switzerland", "Europe"),
    ("Austria", "Europe"), ("Poland", "Europe"), ("Czechia", "Europe"), ("Slovakia", "Europe"),
    ("Hungary", "Europe"), ("Romania", "Europe"), ("Bulgaria", "Europe"), ("Greece", "Europe"),
    ("Croatia", "Europe"), ("Slovenia", "Europe"), ("Serbia", "Europe"), ("Norway", "Europe"),
    ("Sweden", "Europe"), ("Finland", "Europe"), ("Denmark", "Europe"), ("Iceland", "Europe"),
    ("Estonia", "Europe"), ("Latvia", "Europe"), ("Lithuania", "Europe"), ("Ukraine", "Europe"),
    ("Russia", "Europe"), ("Turkey", "Asia"),
    ("United States", "North America"), ("Canada", "North America"), ("Mexico", "North America"),
    ("Guatemala", "North America"), ("Cuba", "North America"), ("Costa Rica", "North America"),
    ("Brazil", "South America"), ("Argentina", "South America"), ("Chile", "South America"),
    ("Peru", "South America"), ("Colombia", "South America"), ("Bolivia", "South America"),
    ("Ecuador", "South America"), ("Uruguay", "South America"),
    ("China", "Asia"), ("Japan", "Asia"), ("South Korea", "Asia"), ("India", "Asia"),
    ("Thailand", "Asia"), ("Vietnam", "Asia"), ("Indonesia", "Asia"), ("Malaysia", "Asia"),
    ("Philippines", "Asia"), ("Singapore", "Asia"), ("Taiwan", "Asia"), ("Cambodia", "Asia"),
    ("Nepal", "Asia"), ("Sri Lanka", "Asia"), ("Pakistan", "Asia"), ("Bangladesh", "Asia"),
    ("Israel", "Asia"), ("Jordan", "Asia"), ("United Arab Emirates", "Asia"),
    ("Saudi Arabia", "Asia"), ("Iran", "Asia"), ("Kazakhstan", "Asia"),
    ("Egypt", "Africa"), ("Morocco", "Africa"), ("Tunisia", "Africa"), ("Algeria", "Africa"),
    ("South Africa", "Africa"), ("Kenya", "Africa"), ("Tanzania", "Africa"), ("Nigeria", "Africa"),
    ("Ghana", "Africa"), ("Ethiopia", "Africa"), ("Namibia", "Africa"), ("Botswana", "Africa"),
    ("Australia", "Oceania"), ("New Zealand", "Oceania"), ("Fiji", "Oceania"),
]

COUNTRY_TO_CONTINENT: dict[str, str] = {name: cont for name, cont in COUNTRIES}
COUNTRY_NAMES: list[str] = [name for name, _ in COUNTRIES]

# English country name -> ISO 3166-1 alpha-2 (lowercase, matches Nominatim's
# address.country_code). Used to cross-check GeoCLIP coordinates against the
# StreetCLIP country ranking regardless of the reverse-geocoder's language.
COUNTRY_TO_CODE: dict[str, str] = {
    "Germany": "de", "France": "fr", "Italy": "it", "Spain": "es", "Portugal": "pt",
    "United Kingdom": "gb", "Ireland": "ie", "Netherlands": "nl", "Belgium": "be",
    "Switzerland": "ch", "Austria": "at", "Poland": "pl", "Czechia": "cz",
    "Slovakia": "sk", "Hungary": "hu", "Romania": "ro", "Bulgaria": "bg",
    "Greece": "gr", "Croatia": "hr", "Slovenia": "si", "Serbia": "rs", "Norway": "no",
    "Sweden": "se", "Finland": "fi", "Denmark": "dk", "Iceland": "is", "Estonia": "ee",
    "Latvia": "lv", "Lithuania": "lt", "Ukraine": "ua", "Russia": "ru", "Turkey": "tr",
    "United States": "us", "Canada": "ca", "Mexico": "mx", "Guatemala": "gt",
    "Cuba": "cu", "Costa Rica": "cr", "Brazil": "br", "Argentina": "ar", "Chile": "cl",
    "Peru": "pe", "Colombia": "co", "Bolivia": "bo", "Ecuador": "ec", "Uruguay": "uy",
    "China": "cn", "Japan": "jp", "South Korea": "kr", "India": "in", "Thailand": "th",
    "Vietnam": "vn", "Indonesia": "id", "Malaysia": "my", "Philippines": "ph",
    "Singapore": "sg", "Taiwan": "tw", "Cambodia": "kh", "Nepal": "np",
    "Sri Lanka": "lk", "Pakistan": "pk", "Bangladesh": "bd", "Israel": "il",
    "Jordan": "jo", "United Arab Emirates": "ae", "Saudi Arabia": "sa", "Iran": "ir",
    "Kazakhstan": "kz", "Egypt": "eg", "Morocco": "ma", "Tunisia": "tn",
    "Algeria": "dz", "South Africa": "za", "Kenya": "ke", "Tanzania": "tz",
    "Nigeria": "ng", "Ghana": "gh", "Ethiopia": "et", "Namibia": "na",
    "Botswana": "bw", "Australia": "au", "New Zealand": "nz", "Fiji": "fj",
}

# StreetCLIP was pretrained on captions phrased like "<...> Street View photo in
# <place>", so matching that phrasing improves its country/region accuracy.
COUNTRY_PROMPT = "a Street View photo in {}"
REGION_PROMPT = "a Street View photo in {}"

# Optional region prompts for a few large countries. Used only to refine the
# "Region" level when the location is pure inference. Still inference (not exact).
REGIONS: dict[str, list[str]] = {
    "Germany": ["Bavaria, Germany", "Berlin, Germany", "Hamburg, Germany",
                "North Rhine-Westphalia, Germany", "Saxony, Germany",
                "Baden-Württemberg, Germany", "Hesse, Germany", "Lower Saxony, Germany"],
    "United States": ["California, USA", "Texas, USA", "Florida, USA", "New York, USA",
                      "Arizona, USA", "Colorado, USA", "Washington State, USA", "Louisiana, USA"],
    "France": ["Île-de-France", "Provence, France", "Brittany, France", "Normandy, France",
               "Occitanie, France", "Auvergne-Rhône-Alpes, France"],
    "Italy": ["Tuscany, Italy", "Sicily, Italy", "Lombardy, Italy", "Veneto, Italy",
              "Lazio, Italy", "Campania, Italy", "Piedmont, Italy"],
    "Spain": ["Andalusia, Spain", "Catalonia, Spain", "Madrid, Spain", "Valencia, Spain",
              "Galicia, Spain", "Basque Country, Spain"],
    "United Kingdom": ["England", "Scotland", "Wales", "Northern Ireland"],
}

# Visual-analysis signal groups. Each maps a human label -> CLIP prompt.
# The fusion step turns the top score of each group into an explainability weight.
SIGNAL_GROUPS: dict[str, dict[str, str]] = {
    "Landschaft": {
        "Küste / Meer": "a photo of a coastline with the sea",
        "Berge": "a photo of a mountain landscape",
        "Wald": "a photo of a dense forest",
        "Wüste": "a photo of a desert",
        "Felder / Ebene": "a photo of open farmland and fields",
        "Stadtlandschaft": "a photo of an urban cityscape",
        "Tropisch": "a photo of a tropical landscape with palm trees",
        "See / Fluss": "a photo of a lake or river",
    },
    "Architektur": {
        "Nordeuropäisch / Backstein": "a photo of north european brick architecture",
        "Mediterran": "a photo of mediterranean architecture with terracotta roofs",
        "Nordamerikanisch (Vorstadt)": "a photo of north american suburban houses",
        "Ostasiatisch": "a photo of east asian architecture",
        "Hochhäuser / modern": "a photo of modern skyscrapers and glass facades",
        "Altstadt / historisch": "a photo of a historic old town",
        "Tropisch / informell": "a photo of informal tropical buildings",
    },
    "Infrastruktur": {
        "Europäische Straßenmarkierung": "a photo of european road markings and signs",
        "US-Straßen / Ampeln": "a photo of north american roads with hanging traffic lights",
        "Linksverkehr": "a photo of a left-hand traffic road",
        "Asiatische Stadtinfrastruktur": "a photo of asian urban street infrastructure",
        "Ländliche Straße": "a photo of a rural road",
        "Bahn / Gleise": "a photo of railway tracks and trains",
    },
    "Klima": {
        "Schnee / Winter": "a snowy winter scene",
        "Trocken / arid": "a dry arid climate scene",
        "Feucht / grün": "a humid lush green climate scene",
        "Gemäßigt": "a temperate climate scene",
        "Tropisch heiß": "a hot tropical climate scene",
    },
}
