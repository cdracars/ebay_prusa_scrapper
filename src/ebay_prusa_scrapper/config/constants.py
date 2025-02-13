"""Constants used throughout the scraper"""

# Official prices
OFFICIAL_PRICES = {
    "MK3S": 799.0,  # kit price
    "MK4": 799.0,   # kit price (fully assembled is often ~1099)
    "MINI": 379.0,  # kit price
    "CORE": 399.0   # Core One price
}

# Price validation thresholds
PRICE_THRESHOLDS = {
    "MK3S": (400, 1200),   # Kit $799, Assembled $1099
    "MK4": (500, 1300),    # Kit $799, Assembled $1099
    "MINI": (250, 500),    # Kit $379, Assembled $459
    "CORE": (300, 500)     # $399 standard price
}

# Keywords for classification
UPGRADE_KEYWORDS = [
    "hotend", "frame", "bear upgrade", "nozzle", "extruder",
    "thermistor", "misumi", "sheet", "fan shroud", "bondtech",
    "thermistor sensor", "pinda", "sensor", "bobbin holder",
    "spool holder", "upgrade", "part", "spare", "component"
]

PRINTER_KEYWORDS = [
    "3d printer", "assembled", "complete kit", "full kit",
    "working printer", "printing", "fully built"
]

# Model detection patterns
MODEL_PATTERNS = {
    "MK3S": [
        r'\bmk3\s*s\+?\b',  # matches mk3s, mk3s+
        r'\bmk3\s+s\+?\b',  # matches mk3 s, mk3 s+
        r'\bi3\s*mk3s\+?\b',  # matches i3 mk3s, i3 mk3s+
        r'prusa\s+mk3s\+?\b'  # matches prusa mk3s, prusa mk3s+
    ],
    "MK4": [
        r'\bmk4\b',  # matches mk4
        r'\bmk\s*4\b',  # matches mk4, mk 4
        r'\bi3\s*mk4\b',  # matches i3 mk4
        r'prusa\s+mk4\b'  # matches prusa mk4
    ],
    "MINI": [
        r'\bmini\+?\b',  # matches mini, mini+
        r'prusa\s+mini\+?\b',  # matches prusa mini, prusa mini+
        r'mini\s*\+\b'  # matches mini+, mini +
    ],
    "CORE": [
        r'\bcore\s*one\b',  # matches core one
        r'\bcore\s*1\b',  # matches core 1
        r'\bcore1\b',  # matches core1
        r'original\s+core\b',  # matches original core
        r'prusa\s+core'  # matches prusa core
    ]
}

UPGRADE_MAX_PRICE = 300  # Maximum reasonable price for upgrades

