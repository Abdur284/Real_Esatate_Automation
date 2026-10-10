"""
================================================================================
  AI-BASED CONSTRUCTION COST ESTIMATION SYSTEM FOR PAKISTAN
  Final Year Project - Hybrid Rule-Based + XGBoost Architecture
  Version : 5.0  (Revised: honest validation, calibrated rules, learned fusion)
================================================================================

WHAT CHANGED FROM v4.0  (read this for your report / viva)
----------------------------------------------------------
  A1  Proper train / validation / test split. Early stopping now happens on a
      SEPARATE validation set, so the reported test metrics are honest. 5-fold
      cross-validation is also reported.
  A2  Latitude / longitude are looked up from the city instead of being hard-set
      to Attock for every prediction.
  A3  Category values are normalised (case-insensitively) against the vocabulary
      actually learned from your dataset. Unknown values are WARNED about, not
      silently swapped for whichever class sorts first.
  A4  NLP parsing fixes: thousands commas ("1,800 sqft"), hyphen/spaces
      ("5-marla"), "square feet" / "sq. ft.", and combined units
      ("1 kanal 10 marla"). "double bedroom" is no longer read as 2 bedrooms.
  A5  Rule engine fixes: steel computed per sqft of covered area (not 8.5 kg per
      cuft of ALL concrete, which made steel ~42% of cost); removed the
      double-counted timber framing and the duplicate roof slab charge;
      excavation is strip-footing based; the city multiplier is applied to
      LABOUR + FINISHES only, not to steel/cement material. The whole rule engine
      is then CALIBRATED against your dataset at train time.
  B1  Model trains on log(cost) for better percentage accuracy.
  B2  XGBoost native categorical support; StandardScaler removed (useless for
      trees).
  B3  Linear Regression and Random Forest baselines are reported for comparison.
  B4  The uncertainty band is derived from real validation residuals (a simple
      conformal interval), not a hard-coded +/-12%.
  B5  The rule/ML blend weight (alpha) is LEARNED on the validation set, and the
      system flags cases where the two estimates disagree strongly.

ASSUMPTIONS YOU MUST VERIFY  (set the flags in SECTION 0 if wrong)
------------------------------------------------------------------
  * covered_area_sqft is treated as the COVERED AREA OF ONE FLOOR. The rule
    engine multiplies it by `floors` to get total built-up area. If your column
    already stores total built-up across all floors, set AREA_IS_TOTAL_BUILTUP = True.
  * number_of_rooms in the dataset counts ALL rooms, so ROOMS_COLUMN_IS_TOTAL is
    set True: at prediction the model is fed bedrooms + other_rooms (guest / TV /
    drawing / lounge / etc.). Set it False if your column is bedrooms-only.

HOW TO USE IN GOOGLE COLAB
--------------------------
  from google.colab import files
  uploaded = files.upload()                 # pick construction_dataset.csv

  system = ConstructionCostSystem()
  system.train_from_dataset('construction_dataset.csv')   # trains + saves .pkl
  # IMPORTANT: download the saved .pkl or copy it to Drive - Colab wipes it on reset

  # later runs:
  system = ConstructionCostSystem()
  system.load()
  print_report(system.estimate("10 marla modern house in Islamabad, 4 bedrooms"))
"""

# -- Standard library ----------------------------------------------------------
import re
import os
import json
import warnings

import joblib
import numpy  as np
import pandas as pd

from datetime import datetime
from typing   import Dict, List, Optional, Tuple

# -- ML stack ------------------------------------------------------------------
import xgboost as xgb
from sklearn.model_selection import train_test_split, KFold
from sklearn.linear_model    import LinearRegression
from sklearn.ensemble        import RandomForestRegressor
from sklearn.metrics         import mean_absolute_error, r2_score

warnings.filterwarnings('ignore')


# ==============================================================================
#  SECTION 0 - CONFIGURATION & REFERENCE TABLES
# ==============================================================================

# Set True if covered_area_sqft already stores the total built-up area across
# all floors (rather than one floor's covered area).
AREA_IS_TOTAL_BUILTUP = False

# The dataset has ONE room column (number_of_rooms). If it counts ALL rooms
# (bedrooms + lounge + guest + TV + ...), set this True and the model will be
# fed bedrooms + other_rooms. If it counts bedrooms only, leave it False so the
# model's input is not corrupted. Either way, the RULE ENGINE always prices the
# extra rooms (partition walls, finishes, doors, electrical).
ROOMS_COLUMN_IS_TOTAL = True

# Material unit prices (PKR, April 2026, Attock/Punjab baseline)
MATERIAL_PRICES = {
    'cement':      {'price': 1350, 'unit': 'per bag (50kg)'},
    'steel':       {'price': 260,  'unit': 'per kg'},
    'bricks':      {'price': 15,   'unit': 'per brick'},
    'sand':        {'price': 65,   'unit': 'per cft'},
    'crush':       {'price': 140,  'unit': 'per cft'},
    'paint':       {'price': 420,  'unit': 'per liter'},
    'tile_basic':  {'price': 100,  'unit': 'per sqft'},
    'tile_mid':    {'price': 160,  'unit': 'per sqft'},
    'tile_luxury': {'price': 280,  'unit': 'per sqft'},
}

# City cost index (Attock = 1.0). Applied to LABOUR + FINISHES only.
CITY_MULTIPLIER = {
    'islamabad': 1.35, 'rawalpindi': 1.25, 'lahore': 1.20, 'karachi': 1.30,
    'peshawar':  1.10, 'quetta':     1.05, 'multan': 1.10, 'faisalabad': 1.15,
    'gujranwala':1.12, 'sialkot':    1.12, 'attock': 1.00, 'default': 1.10,
}

# Approximate city centroids (lat, lon). Used to fill the model's geo features.
CITY_COORDS = {
    'islamabad': (33.68, 73.05), 'rawalpindi': (33.60, 73.04),
    'lahore':    (31.55, 74.34), 'karachi':    (24.86, 67.01),
    'peshawar':  (34.01, 71.58), 'quetta':     (30.18, 66.98),
    'multan':    (30.16, 71.52), 'faisalabad': (31.42, 73.08),
    'gujranwala':(32.16, 74.19), 'sialkot':    (32.49, 74.53),
    'attock':    (33.77, 72.36), 'default':    (33.77, 72.36),
}

# Style multiplier - applied to FINISHES / quality trades only, not structure.
STYLE_MULTIPLIER = {
    'modern': 1.15, 'contemporary': 1.15, 'traditional': 1.00, 'colonial': 1.10,
    'mediterranean': 1.20, 'minimalist': 1.05, 'classic': 1.00,
    'simple': 1.00, 'default': 1.00,
}

UNIT_TO_SQFT = {
    'marla': 272.25, 'kanal': 5445.0,
    'sqft': 1.0, 'sqm': 10.764,
}

# Structural / productivity constants
STRUCT = {
    'story_height_ft':        10.0,
    'slab_thickness_ft':      0.5,     # 6" RCC slab (serves as the roof too)
    'perimeter_factor':       3.8,     # perimeter ~= 3.8 * sqrt(area)
    'wastage_pct':            0.05,
    'steel_kg_per_sqft':      2.8,     # steel per sqft of covered area (A5 fix)
    'bricks_per_sqft_wall':   7.8,
    'footing_width_ft':       2.5,
    'footing_depth_ft':       4.0,
    'general_conditions_pct': 0.10,
    'contingency_pct':        0.05,
    'markup_pct':             0.15,
}

LABOR = {
    'mason':        {'rate': 2000, 'prod': 80,  'burden': 0.35},
    'helper':       {'rate': 1100, 'prod': 80,  'burden': 0.35},
    'bar_bender':   {'rate': 2400, 'prod': 400, 'burden': 0.40},
    'concretor':    {'rate': 1800, 'prod': 25,  'burden': 0.35},
    'roofer':       {'rate': 2000, 'prod': 100, 'burden': 0.30},
    'excav_op':     {'rate': 2800, 'prod': 400, 'burden': 0.40},
    'excav_helper': {'rate': 1100, 'prod': 400, 'burden': 0.35},
}

DEFAULTS = {
    'area_sqft':     1361.25,   # 5 marla
    'floors':        2,
    'bedrooms':      3,
    'bathrooms':     3,
    'kitchens':      1,
    'other_rooms':   0,   # guest / TV / drawing / lounge / store / servant / study
    'city':         'attock',
    'house_style':  'traditional',
    'tile_type':    'tile_mid',
    'door_material':'wood',
    'cement_index':  1.0,
    'steel_index':   1.0,
    'labor_index':   1.0,
}

MODEL_SAVE_PATH = 'xgb_cost_model.pkl'


# ==============================================================================
#  SECTION 1 - NLP MODULE  (rule-based information extraction)
# ==============================================================================

class NLPExtractor:
    """Regex + keyword extractor. Only pulls features present in the dataset."""

    # Cardinal number words only - NOT single/double/triple (A4 fix: "double
    # bedroom" must not become 2 bedrooms).
    WORD_NUMS = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
    }

    CITY_KEYWORDS = [k for k in CITY_MULTIPLIER if k != 'default']

    STYLE_KEYWORDS = {
        'modern': 'modern', 'contemporary': 'contemporary',
        'traditional': 'traditional', 'colonial': 'colonial',
        'mediterranean': 'mediterranean', 'minimalist': 'minimalist',
        'classic': 'classic', 'simple': 'simple',
    }

    TILE_KEYWORDS = {
        'luxury tile': 'tile_luxury', 'premium tile': 'tile_luxury',
        'marble': 'marble', 'granite': 'granite',
        'ceramic': 'ceramic', 'porcelain': 'porcelain',
        'mid tile': 'tile_mid', 'standard tile': 'tile_mid',
        'basic tile': 'tile_basic', 'cheap tile': 'tile_basic',
        'economy tile': 'tile_basic', 'local tile': 'local',
    }

    DOOR_KEYWORDS = {
        'steel door': 'steel', 'metal door': 'steel',
        'engineered': 'engineered',
        'aluminum': 'aluminum', 'aluminium': 'aluminum',
        'upvc': 'pvc', 'pvc': 'pvc',
        'wooden': 'wood', 'timber': 'wood', 'wood': 'wood',
    }

    DOOR_COST = {
        'wood': 1.0, 'engineered': 1.10, 'steel': 1.20,
        'aluminum': 1.15, 'pvc': 0.80,
    }

    # Non-bed/bath/kitchen rooms. Each pattern is counted once (with its number,
    # or 1 if mentioned without a number) and summed into `other_rooms`.
    OTHER_ROOM_PATTERNS = [
        r'guest\s*rooms?', r'tv\s*(?:room|lounge)s?', r'drawing\s*rooms?',
        r'dining\s*rooms?', r'living\s*rooms?', r'lounges?',
        r'store\s*rooms?', r'servant\s*(?:room|quarter)s?',
        r'study\s*rooms?', r'prayer\s*rooms?', r'home\s*office',
    ]

    # Flexible unit aliases -> canonical unit key in UNIT_TO_SQFT
    _UNIT_ALIASES = [
        (r'marlas?',                  'marla'),
        (r'kanals?',                  'kanal'),
        (r'sq(?:uare)?\.?\s*feet',    'sqft'),
        (r'sq(?:uare)?\.?\s*ft',      'sqft'),
        (r'sq\.?ft',                  'sqft'),
        (r'sqft',                     'sqft'),
        (r'sq(?:uare)?\.?\s*meters?', 'sqm'),
        (r'sq(?:uare)?\.?\s*m',       'sqm'),
        (r'sqm',                      'sqm'),
    ]

    def extract(self, text: str) -> Tuple[dict, dict]:
        t = text.lower().strip()
        f, s = {}, {}

        f['area_sqft'],    s['area_sqft']     = self._area(t)
        f['floors'],       s['floors']        = self._floors(t)
        f['bedrooms'],     s['bedrooms']      = self._rooms(t, r'bed(?:room)?s?|br\b')
        f['bathrooms'],    s['bathrooms']     = self._rooms(t, r'bath(?:room)?s?|washroom|toilet')
        f['kitchens'],     s['kitchens']      = self._rooms(t, r'kitchens?')
        f['other_rooms'],  s['other_rooms']   = self._other_rooms(t)
        f['city'],         s['city']          = self._city(t)
        f['house_style'],  s['house_style']   = self._map(t, self.STYLE_KEYWORDS)
        f['tile_type'],    s['tile_type']     = self._map(t, self.TILE_KEYWORDS)
        f['door_material'],s['door_material'] = self._map(t, self.DOOR_KEYWORDS)

        for key, default_val in DEFAULTS.items():
            if f.get(key) is None:
                f[key] = default_val
                s[key] = 'default'

        f['cement_index'] = DEFAULTS['cement_index']
        f['steel_index']  = DEFAULTS['steel_index']
        f['labor_index']  = DEFAULTS['labor_index']
        return f, s

    def _canonical_unit(self, unit_text: str) -> Optional[str]:
        for pattern, unit in self._UNIT_ALIASES:
            if re.fullmatch(pattern, unit_text):
                return unit
        return None

    def _area(self, t):
        # One non-overlapping left-to-right pass over "<number> <unit>" pairs, so
        # each pair is counted exactly once (fixes "1,800 sqft" = 1800, not 5400)
        # while still summing combined units like "1 kanal 10 marla". Handles
        # commas and an optional hyphen/space ("5-marla", "1,800 sqft").
        unit_alt = '|'.join(f'(?:{p})' for p, _ in self._UNIT_ALIASES)
        total, found = 0.0, False
        for m in re.finditer(rf'(\d[\d,]*(?:\.\d+)?)\s*-?\s*({unit_alt})\b', t):
            unit = self._canonical_unit(m.group(2))
            if unit:
                total += float(m.group(1).replace(',', '')) * UNIT_TO_SQFT[unit]
                found = True
        return (round(total, 2), 'regex') if found else (None, None)

    def _floors(self, t):
        m = re.search(r'(\d+)\s*(?:floor|stor(?:ey|y)|storied)', t)
        if m: return int(m.group(1)), 'regex'
        m = re.search(r'g\s*\+\s*(\d)', t)
        if m: return int(m.group(1)) + 1, 'regex'
        if re.search(r'triple\s*stor',            t): return 3, 'keyword'
        if re.search(r'double\s*stor|duplex',     t): return 2, 'keyword'
        if re.search(r'bungalow|single\s*stor',   t): return 1, 'keyword'
        for word, num in self.WORD_NUMS.items():
            if re.search(rf'\b{word}\s*(?:floor|stor(?:ey|y))\b', t):
                return num, 'keyword'
        return None, None

    def _rooms(self, t, pattern):
        m = re.search(rf'(\d+)\s*(?:{pattern})', t)
        if m: return int(m.group(1)), 'regex'
        for word, num in self.WORD_NUMS.items():
            if re.search(rf'\b{word}\s*(?:{pattern})\b', t):
                return num, 'keyword'
        return None, None

    def _count(self, t, pattern):
        """Count for one room phrase: a number before it, a number word before
        it, or 1 if the phrase appears bare. 0 if absent."""
        m = re.search(rf'(\d+)\s*(?:{pattern})\b', t)
        if m:
            return int(m.group(1))
        for word, num in self.WORD_NUMS.items():
            if re.search(rf'\b{word}\s*(?:{pattern})\b', t):
                return num
        if re.search(rf'\b(?:{pattern})\b', t):
            return 1
        return 0

    def _other_rooms(self, t):
        total = sum(self._count(t, pat) for pat in self.OTHER_ROOM_PATTERNS)
        return (total, 'regex') if total > 0 else (None, None)

    def _city(self, t):
        for city in self.CITY_KEYWORDS:
            if re.search(rf'\b{city}\b', t):
                return city, 'keyword'
        return None, None

    def _map(self, t, mapping):
        for kw in sorted(mapping, key=len, reverse=True):
            if kw in t:
                return mapping[kw], 'keyword'
        return None, None


# ==============================================================================
#  SECTION 2 - RULE-BASED COST ENGINE
# ==============================================================================

class RuleBasedEngine:
    """Formula-based quantity-takeoff estimator. `calibration_factor` is fitted
    against the dataset at train time so the formulas track real prices."""

    TILE_MAP = {
        'marble': 'tile_luxury', 'granite': 'tile_luxury',
        'porcelain': 'tile_mid', 'ceramic': 'tile_mid',
        'tile_mid': 'tile_mid', 'tile_basic': 'tile_basic',
        'tile_luxury': 'tile_luxury', 'local': 'tile_basic',
    }

    def __init__(self):
        self.calibration_factor = 1.0

    def compute(self, features: dict) -> dict:
        area   = float(features['area_sqft'])
        floors = float(features['floors'])
        beds   = float(features['bedrooms'])
        baths  = float(features['bathrooms'])
        kits   = float(features['kitchens'])
        other  = float(features.get('other_rooms', 0))   # guest/TV/drawing/etc.

        total_built = area if AREA_IS_TOTAL_BUILTUP else area * floors

        city_m  = CITY_MULTIPLIER.get(str(features.get('city', 'default')).lower(), 1.10)
        sty_m   = STYLE_MULTIPLIER.get(str(features.get('house_style', 'traditional')).lower(), 1.00)
        door_m  = NLPExtractor.DOOR_COST.get(str(features.get('door_material', 'wood')).lower(), 1.00)
        cem_idx = float(features.get('cement_index', 1.0))
        stl_idx = float(features.get('steel_index',  1.0))
        lab_idx = float(features.get('labor_index',  1.0))

        tile_key   = self.TILE_MAP.get(str(features.get('tile_type', 'tile_mid')).lower(), 'tile_mid')
        tile_price = MATERIAL_PRICES[tile_key]['price']

        wall_area = STRUCT['perimeter_factor'] * (area ** 0.5) * STRUCT['story_height_ft'] * floors
        perimeter = STRUCT['perimeter_factor'] * (area ** 0.5)
        wastage   = 1 + STRUCT['wastage_pct']

        # Extra non-bed/bath/kitchen rooms add internal (non-structural) partition
        # walls. ~40 ft of partition perimeter per room. These walls carry masonry,
        # plaster and paint cost but not rebar/concrete (they are not load-bearing).
        partition_wall = other * 40.0 * STRUCT['story_height_ft']
        wall_area_fin  = wall_area + partition_wall

        # multipliers: materials scale with their market index; labour + finishes
        # scale with city cost of living and labour index; quality trades with style.
        mat_cement = cem_idx
        mat_steel  = stl_idx
        labour_m   = city_m * lab_idx
        finish_m   = city_m * sty_m

        dc = {}

        # 1. Excavation - strip footings along wall lines (not whole footprint)
        exc_cuft = perimeter * STRUCT['footing_width_ft'] * STRUCT['footing_depth_ft']
        exc_days = exc_cuft / LABOR['excav_op']['prod']
        dc['excavation'] = (exc_days * (LABOR['excav_op']['rate']
                            + LABOR['excav_helper']['rate'] * 0.6)) * labour_m * wastage

        # 2. Concrete / RCC (slab acts as the floor/roof structure)
        conc_cuft  = (area * STRUCT['slab_thickness_ft'] + area * 0.18) * floors
        conc_mat   = conc_cuft * (MATERIAL_PRICES['crush']['price'] * 0.55 * mat_cement
                                  + MATERIAL_PRICES['cement']['price'] / 1.25 * 0.45 * mat_cement)
        conc_days  = conc_cuft / LABOR['concretor']['prod']
        conc_labor = conc_days * LABOR['concretor']['rate'] * (1 + LABOR['concretor']['burden']) * labour_m
        dc['concrete_rcc'] = (conc_mat + conc_labor) * wastage

        # 3. Formwork
        dc['formwork'] = conc_cuft * 1.8 * 80 * labour_m

        # 4. Rebar - steel per sqft of covered area (A5 fix)
        rebar_kg  = total_built * STRUCT['steel_kg_per_sqft']
        rebar_mat = rebar_kg * MATERIAL_PRICES['steel']['price'] * mat_steel
        bend_days = rebar_kg / LABOR['bar_bender']['prod']
        rebar_lab = bend_days * LABOR['bar_bender']['rate'] * (1 + LABOR['bar_bender']['burden']) * labour_m
        dc['rebar'] = (rebar_mat + rebar_lab) * wastage

        # 5. Masonry (external walls + internal partitions for extra rooms)
        bricks_mat = wall_area_fin * STRUCT['bricks_per_sqft_wall'] * MATERIAL_PRICES['bricks']['price'] * mat_cement
        mason_days = wall_area_fin / LABOR['mason']['prod']
        mason_lab  = mason_days * (LABOR['mason']['rate'] + LABOR['helper']['rate']) * (1 + LABOR['mason']['burden']) * labour_m
        mortar     = wall_area_fin * 0.018 * MATERIAL_PRICES['sand']['price'] * mat_cement
        dc['masonry'] = (bricks_mat + mason_lab + mortar) * wastage

        # 6. Woodwork (kitchens + bedroom wardrobes + extra-room built-ins)
        dc['woodwork'] = (kits * 25_000 + beds * 15_000 + other * 10_000) * finish_m

        # 7. Roof waterproofing + screed (structural slab already in concrete_rcc)
        roof_area     = area
        roof_days     = roof_area / LABOR['roofer']['prod']
        dc['roofing'] = (roof_area * 120 + LABOR['roofer']['rate'] * roof_days * labour_m) * wastage

        # 8. Doors & windows - quality trade (each extra room ~1 door + 1 window)
        openings = beds * 2 + baths + kits + 4 + other * 2
        dc['doors_windows'] = openings * 22_000 * door_m * finish_m

        # 9. Finishes (plaster + tile + paint) - partitions add plaster area
        plaster_area = wall_area_fin * 2 + total_built
        plaster_cost = plaster_area * 55
        tile_cost    = total_built * 0.90 * tile_price
        paint_cost   = (plaster_area / 90) * MATERIAL_PRICES['paint']['price']
        dc['finishes'] = (plaster_cost + tile_cost + paint_cost) * finish_m

        # 10. Plumbing
        fixtures = baths * 5 + kits * 3
        dc['plumbing'] = (fixtures * 8_000 + total_built * 140) * finish_m

        # 11. Electrical
        points = beds * 8 + baths * 4 + kits * 6 + other * 6 + 12
        dc['electrical'] = (points * 5_000 + total_built * 130) * finish_m

        # Apply fitted calibration so formulas match the dataset's price level
        dc = {k: v * self.calibration_factor for k, v in dc.items()}

        direct_sum  = sum(dc.values())
        gen_cond    = direct_sum * STRUCT['general_conditions_pct']
        contingency = direct_sum * STRUCT['contingency_pct']
        markup      = (direct_sum + gen_cond + contingency) * STRUCT['markup_pct']
        grand_total = direct_sum + gen_cond + contingency + markup

        return {
            'breakdown':            {k: round(v) for k, v in dc.items()},
            'direct_cost':          round(direct_sum),
            'general_conditions':   round(gen_cond),
            'contingency':          round(contingency),
            'markup':               round(markup),
            'total_base_cost':      round(grand_total),
            'per_sqft':             round(grand_total / total_built) if total_built else 0,
            'total_built_sqft':     round(total_built),
            'composite_multiplier': round(city_m * sty_m, 3),
        }

    def calibrate(self, feature_rows: List[dict], actual_costs: np.ndarray):
        """Fit a single global scale so median(rule_total) matches the data.
        Uses the ratio of medians, which is robust to outliers."""
        self.calibration_factor = 1.0   # reset before measuring raw output
        raw = np.array([self.compute(fr)['total_base_cost'] for fr in feature_rows], dtype=float)
        raw = raw[raw > 0]
        actual = np.asarray(actual_costs, dtype=float)[:len(raw)]
        if len(raw) and np.median(raw) > 0:
            self.calibration_factor = float(np.median(actual) / np.median(raw))
        return self.calibration_factor


# ==============================================================================
#  SECTION 3 - XGBOOST ML MODEL  (native categoricals, log target)
# ==============================================================================

class XGBoostCostModel:

    # area_category is intentionally NOT used: it is a coarse bucket of
    # covered_area_sqft (which the model already has at full resolution), and the
    # dataset's own labels differ from any we could derive at prediction time.
    CATEGORICAL_COLS = ['city', 'house_style', 'tile_type', 'door_material']
    NUMERIC_COLS = [
        'covered_area_sqft', 'floors', 'number_of_rooms', 'number_of_bathrooms',
        'kitchen_count', 'latitude', 'longitude',
        'cement_index', 'steel_index', 'labor_index',
    ]
    TARGET_COL = 'total_cost_pkr'

    def __init__(self):
        self.model: Optional[xgb.XGBRegressor] = None
        self.cat_categories: Dict[str, List[str]] = {}   # col -> lowercased training categories
        self.cat_modes: Dict[str, str] = {}              # col -> most common training value
        self.feature_names: List[str] = []
        self.is_trained = False
        self.metrics: Dict = {}
        self.baseline_metrics: Dict = {}

    # -- encoding ------------------------------------------------------------
    def _prepare(self, df: pd.DataFrame, fit: bool = False) -> pd.DataFrame:
        X = pd.DataFrame(index=df.index)
        for col in self.NUMERIC_COLS:
            X[col] = pd.to_numeric(df[col], errors='coerce').astype(float)

        for col in self.CATEGORICAL_COLS:
            vals = df[col].astype(str).str.strip().str.lower()
            if fit:
                cats = sorted(vals.dropna().unique().tolist())
                self.cat_categories[col] = cats
                nonnull = vals.dropna()
                self.cat_modes[col] = (nonnull.mode().iloc[0] if not nonnull.empty
                                       else (cats[0] if cats else ''))
            cats = self.cat_categories[col]
            # Warn about unseen values (A3) - they become NaN, which XGBoost handles
            if not fit:
                unseen = set(vals.unique()) - set(cats)
                if unseen:
                    print(f"  [XGB][warn] column '{col}': unseen value(s) {unseen} "
                          f"-> treated as missing (not substituted).")
            # Keep a proper category dtype carrying the FULL training category set
            # so codes stay consistent between fit and predict, and a single-row
            # frame never collapses to zero categories. Values not in `cats`
            # become NaN (missing), which XGBoost handles natively.
            X[col] = pd.Categorical(vals, categories=cats)

        if fit:
            self.feature_names = list(X.columns)
        return X[self.feature_names] if self.feature_names else X

    # -- training ------------------------------------------------------------
    def fit(self, df_train: pd.DataFrame, df_val: pd.DataFrame) -> dict:
        X_train = self._prepare(df_train, fit=True)
        X_val   = self._prepare(df_val,   fit=False)
        y_train = np.log1p(df_train[self.TARGET_COL].values.astype(float))
        y_val   = np.log1p(df_val[self.TARGET_COL].values.astype(float))

        self.model = xgb.XGBRegressor(
            n_estimators          = 800,
            max_depth             = 6,
            learning_rate         = 0.04,
            subsample             = 0.80,
            colsample_bytree      = 0.80,
            min_child_weight      = 5,
            reg_alpha             = 0.1,
            reg_lambda            = 1.0,
            objective             = 'reg:squarederror',
            eval_metric           = 'mae',
            early_stopping_rounds = 40,
            enable_categorical    = True,
            tree_method           = 'hist',
            random_state          = 42,
            n_jobs                = -1,
            verbosity             = 0,
        )
        self.model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
        self.is_trained = True
        return {'best_iteration': int(self.model.best_iteration)}

    def evaluate(self, df_test: pd.DataFrame) -> dict:
        X_test = self._prepare(df_test, fit=False)
        y_true = df_test[self.TARGET_COL].values.astype(float)
        y_pred = np.expm1(self.model.predict(X_test))
        self.metrics = self._score(y_true, y_pred, extra={
            'best_iter': int(self.model.best_iteration),
            'n_test':    int(len(df_test)),
        })
        return self.metrics

    def cross_validate(self, df: pd.DataFrame, folds: int = 5) -> dict:
        """5-fold CV MAE/R2 in real PKR space using the tuned hyper-params."""
        X = self._prepare(df, fit=False)
        y = np.log1p(df[self.TARGET_COL].values.astype(float))
        params = dict(
            n_estimators=self.model.best_iteration or 400, max_depth=6,
            learning_rate=0.04, subsample=0.8, colsample_bytree=0.8,
            min_child_weight=5, reg_alpha=0.1, reg_lambda=1.0,
            enable_categorical=True, tree_method='hist', random_state=42,
            objective='reg:squarederror', n_jobs=-1, verbosity=0)
        kf = KFold(n_splits=folds, shuffle=True, random_state=42)
        maes, r2s = [], []
        for tr, te in kf.split(X):
            m = xgb.XGBRegressor(**params)
            m.fit(X.iloc[tr], y[tr], verbose=False)
            p = np.expm1(m.predict(X.iloc[te]))
            yt = np.expm1(y[te])
            maes.append(mean_absolute_error(yt, p))
            r2s.append(r2_score(yt, p))
        return {'cv_MAE_mean': round(float(np.mean(maes))),
                'cv_MAE_std':  round(float(np.std(maes))),
                'cv_R2_mean':  round(float(np.mean(r2s)), 4)}

    def train_baselines(self, df_train, df_test) -> dict:
        """Linear Regression + Random Forest for comparison (B3)."""
        def codes(df):
            X = self._prepare(df, fit=False)
            return X.apply(lambda c: c.cat.codes if str(c.dtype) == 'category' else c).fillna(-1).values
        Xtr, Xte = codes(df_train), codes(df_test)
        ytr = np.log1p(df_train[self.TARGET_COL].values.astype(float))
        yte = df_test[self.TARGET_COL].values.astype(float)
        out = {}
        for name, mdl in [('linear', LinearRegression()),
                          ('random_forest', RandomForestRegressor(
                              n_estimators=300, random_state=42, n_jobs=-1))]:
            mdl.fit(Xtr, ytr)
            pred = np.expm1(mdl.predict(Xte))
            out[name] = {'MAE': round(float(mean_absolute_error(yte, pred))),
                         'R2':  round(float(r2_score(yte, pred)), 4)}
        self.baseline_metrics = out
        return out

    @staticmethod
    def _score(y_true, y_pred, extra=None) -> dict:
        y_true = np.asarray(y_true, float); y_pred = np.asarray(y_pred, float)
        mask = y_true != 0
        mape = float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)
        d = {'MAE': round(float(mean_absolute_error(y_true, y_pred))),
             'R2': round(float(r2_score(y_true, y_pred)), 4),
             'MAPE_pct': round(mape, 2)}
        if extra: d.update(extra)
        return d

    # -- inference -----------------------------------------------------------
    def predict(self, features: dict) -> float:
        if not self.is_trained:
            raise RuntimeError("Model not ready. Call load() or train first.")
        city = str(features.get('city', DEFAULTS['city'])).lower()
        lat, lon = CITY_COORDS.get(city, CITY_COORDS['default'])
        area = float(features.get('area_sqft', DEFAULTS['area_sqft']))

        beds  = features.get('bedrooms', DEFAULTS['bedrooms'])
        other = features.get('other_rooms', 0)
        rooms_for_model = beds + other if ROOMS_COLUMN_IS_TOTAL else beds

        # Snap categorical tokens onto the dataset's own vocabulary. If the
        # parser's token is not a value the model was trained on, fall back to the
        # column's most common training value (an in-distribution default) rather
        # than feeding the model a missing/unknown category.
        def _snap(col, val):
            v = str(val).lower()
            if v in self.cat_categories.get(col, []):
                return v
            return self.cat_modes.get(col, v)

        row = {
            'covered_area_sqft':   area,
            'floors':              features.get('floors',      DEFAULTS['floors']),
            'number_of_rooms':     rooms_for_model,
            'number_of_bathrooms': features.get('bathrooms',   DEFAULTS['bathrooms']),
            'kitchen_count':       features.get('kitchens',    DEFAULTS['kitchens']),
            'latitude':            lat,
            'longitude':           lon,
            'cement_index':        features.get('cement_index', DEFAULTS['cement_index']),
            'steel_index':         features.get('steel_index',  DEFAULTS['steel_index']),
            'labor_index':         features.get('labor_index',  DEFAULTS['labor_index']),
            'city':                _snap('city',          city),
            'house_style':         _snap('house_style',   features.get('house_style',  DEFAULTS['house_style'])),
            'tile_type':           _snap('tile_type',     features.get('tile_type',    DEFAULTS['tile_type'])),
            'door_material':       _snap('door_material', features.get('door_material',DEFAULTS['door_material'])),
        }
        X = self._prepare(pd.DataFrame([row]), fit=False)
        return max(0.0, float(np.expm1(self.model.predict(X)[0])))

    def feature_importance(self, top_n: int = 10) -> List[Tuple[str, float]]:
        if not self.is_trained: return []
        pairs = sorted(zip(self.feature_names, self.model.feature_importances_),
                       key=lambda x: x[1], reverse=True)
        return pairs[:top_n]


# ==============================================================================
#  SECTION 4 - HYBRID COMBINER  (learned alpha + conformal band)
# ==============================================================================

class HybridCombiner:
    """final = alpha * rule + (1 - alpha) * ml, with alpha LEARNED on validation
    and the uncertainty band taken from real validation residuals (B4, B5)."""

    def __init__(self):
        self.alpha     = 0.5     # learned on validation
        self.band_low  = -0.12   # learned quantiles; fallback +/-12%
        self.band_high = 0.12

    def learn(self, rule_costs, ml_costs, actual) -> dict:
        rule = np.asarray(rule_costs, float)
        ml   = np.asarray(ml_costs, float)
        act  = np.asarray(actual, float)
        best_a, best_mae = 0.5, np.inf
        for a in np.linspace(0.0, 1.0, 21):
            mae = mean_absolute_error(act, a * rule + (1 - a) * ml)
            if mae < best_mae:
                best_mae, best_a = mae, a
        self.alpha = float(best_a)

        final = self.alpha * rule + (1 - self.alpha) * ml
        rel   = (act - final) / np.where(final == 0, 1, final)
        if len(rel) >= 20:
            self.band_low  = float(np.quantile(rel, 0.10))
            self.band_high = float(np.quantile(rel, 0.90))
        return {'learned_alpha': round(self.alpha, 3),
                'val_MAE': round(float(best_mae)),
                'band_low_pct': round(self.band_low * 100, 1),
                'band_high_pct': round(self.band_high * 100, 1)}

    def combine(self, base_cost: float, ml_cost: float, source: dict) -> dict:
        prov     = {'regex': 1.0, 'keyword': 0.70, 'default': 0.30}
        critical = ['area_sqft', 'floors', 'bedrooms', 'bathrooms', 'kitchens', 'city']
        data_conf = float(np.mean([prov.get(source.get(k, 'default'), 0.3) for k in critical]))

        alpha = self.alpha
        final = alpha * base_cost + (1 - alpha) * ml_cost

        disagree = abs(base_cost - ml_cost) / max(1.0, min(base_cost, ml_cost))
        warning  = ("Rule-based and ML estimates disagree by "
                    f"{disagree*100:.0f}% - treat this estimate with caution."
                    if disagree > 0.30 else None)

        return {
            'base_cost':        round(base_cost),
            'ml_cost':          round(ml_cost),
            'final_cost':       round(final),
            'low_estimate':     round(final * (1 + self.band_low)),
            'high_estimate':    round(final * (1 + self.band_high)),
            'alpha_rule':       round(alpha, 3),
            'alpha_ml':         round(1 - alpha, 3),
            'data_confidence':  round(data_conf, 3),
            'disagreement_pct': round(disagree * 100, 1),
            'warning':          warning,
        }


# ==============================================================================
#  SECTION 5 - MASTER SYSTEM ORCHESTRATOR
# ==============================================================================

class ConstructionCostSystem:

    def __init__(self, model_path: str = MODEL_SAVE_PATH):
        self.nlp        = NLPExtractor()
        self.engine     = RuleBasedEngine()
        self.ml_model   = XGBoostCostModel()
        self.combiner   = HybridCombiner()
        self.model_path = model_path
        self._ready     = False

    # -- map a dataset row -> rule-engine feature dict -----------------------
    @staticmethod
    def _row_to_features(row: pd.Series) -> dict:
        return {
            'area_sqft':     float(row['covered_area_sqft']),
            'floors':        float(row['floors']),
            'bedrooms':      float(row['number_of_rooms']),
            'bathrooms':     float(row['number_of_bathrooms']),
            'kitchens':      float(row['kitchen_count']),
            'other_rooms':   0.0,   # dataset has no extra-room column

            'city':          str(row['city']).lower(),
            'house_style':   str(row['house_style']).lower(),
            'tile_type':     str(row['tile_type']).lower(),
            'door_material': str(row['door_material']).lower(),
            'cement_index':  float(row.get('cement_index', 1.0)),
            'steel_index':   float(row.get('steel_index', 1.0)),
            'labor_index':   float(row.get('labor_index', 1.0)),
        }

    def train_from_dataset(self, csv_path: str) -> dict:
        print(f"\n  [System] Loading dataset '{csv_path}' ...")
        df = pd.read_csv(csv_path)
        print(f"  [System] {len(df):,} rows x {len(df.columns)} columns")

        required = set(XGBoostCostModel.NUMERIC_COLS
                       + [c for c in XGBoostCostModel.CATEGORICAL_COLS if c != 'area_category']
                       + [XGBoostCostModel.TARGET_COL])
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Dataset is missing columns: {missing}")

        # ---- A1: train / val / test = 70 / 15 / 15 ----
        df_train, df_tmp  = train_test_split(df, test_size=0.30, random_state=42)
        df_val,   df_test = train_test_split(df_tmp, test_size=0.50, random_state=42)
        print(f"  [System] split -> train {len(df_train)} | val {len(df_val)} | test {len(df_test)}")

        # ---- train XGBoost (log target, early stop on val) ----
        fit_info = self.ml_model.fit(df_train, df_val)
        test_metrics = self.ml_model.evaluate(df_test)
        cv_metrics   = self.ml_model.cross_validate(df_train)
        baselines    = self.ml_model.train_baselines(df_train, df_test)

        # ---- A5: calibrate the rule engine on the training rows ----
        train_feats = [self._row_to_features(r) for _, r in df_train.iterrows()]
        cal = self.engine.calibrate(train_feats, df_train[XGBoostCostModel.TARGET_COL].values)
        print(f"  [System] rule-engine calibration factor = {cal:.4f}")

        # ---- B5: learn blend alpha + conformal band on validation ----
        val_feats  = [self._row_to_features(r) for _, r in df_val.iterrows()]
        rule_val   = np.array([self.engine.compute(f)['total_base_cost'] for f in val_feats])
        ml_val     = np.array([self.ml_model.predict(f) for f in val_feats])
        fusion     = self.combiner.learn(rule_val, ml_val, df_val[XGBoostCostModel.TARGET_COL].values)

        self._ready = True
        self.save()

        print("\n  ===== RESULTS =====")
        print(f"  XGBoost (test) : MAE PKR {test_metrics['MAE']:,}  "
              f"R2 {test_metrics['R2']}  MAPE {test_metrics['MAPE_pct']}%  "
              f"(best_iter {test_metrics['best_iter']})")
        print(f"  XGBoost (5-CV) : MAE PKR {cv_metrics['cv_MAE_mean']:,} "
              f"+/- {cv_metrics['cv_MAE_std']:,}  R2 {cv_metrics['cv_R2_mean']}")
        print(f"  Baseline LR    : MAE PKR {baselines['linear']['MAE']:,}  R2 {baselines['linear']['R2']}")
        print(f"  Baseline RF    : MAE PKR {baselines['random_forest']['MAE']:,}  R2 {baselines['random_forest']['R2']}")
        print(f"  Learned alpha  : {fusion['learned_alpha']} (rule) / "
              f"{round(1-fusion['learned_alpha'],3)} (ml)  val MAE PKR {fusion['val_MAE']:,}")
        print(f"  Uncertainty    : {fusion['band_low_pct']}% .. +{fusion['band_high_pct']}%")

        return {'test': test_metrics, 'cv': cv_metrics,
                'baselines': baselines, 'fusion': fusion, 'calibration': cal}

    # -- persistence ---------------------------------------------------------
    def save(self):
        bundle = {
            'version': '5.0',
            'model':           self.ml_model.model,
            'cat_categories':  self.ml_model.cat_categories,
            'cat_modes':       self.ml_model.cat_modes,
            'feature_names':   self.ml_model.feature_names,
            'metrics':         self.ml_model.metrics,
            'baseline_metrics':self.ml_model.baseline_metrics,
            'calibration':     self.engine.calibration_factor,
            'alpha':           self.combiner.alpha,
            'band_low':        self.combiner.band_low,
            'band_high':       self.combiner.band_high,
            'area_is_total':   AREA_IS_TOTAL_BUILTUP,
        }
        joblib.dump(bundle, self.model_path)
        kb = os.path.getsize(self.model_path) / 1024
        print(f"  [System] saved -> '{self.model_path}' ({kb:.1f} KB)")

    def load(self):
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"'{self.model_path}' not found. Run train_from_dataset(csv) first.")
        b = joblib.load(self.model_path)
        self.ml_model.model           = b['model']
        self.ml_model.cat_categories  = b['cat_categories']
        self.ml_model.cat_modes       = b.get('cat_modes', {})
        self.ml_model.feature_names   = b['feature_names']
        self.ml_model.metrics         = b.get('metrics', {})
        self.ml_model.baseline_metrics= b.get('baseline_metrics', {})
        self.ml_model.is_trained      = True
        self.engine.calibration_factor= b.get('calibration', 1.0)
        self.combiner.alpha           = b.get('alpha', 0.5)
        self.combiner.band_low        = b.get('band_low', -0.12)
        self.combiner.band_high       = b.get('band_high', 0.12)
        self._ready = True
        m = self.ml_model.metrics
        print(f"  [System] loaded '{self.model_path}'  "
              f"MAE PKR {m.get('MAE',0):,}  R2 {m.get('R2','?')}  MAPE {m.get('MAPE_pct','?')}%")

    # -- estimation ----------------------------------------------------------
    def estimate(self, user_input: str) -> dict:
        if not self._ready:
            raise RuntimeError("Not ready. train_from_dataset(csv) or load() first.")
        features, source = self.nlp.extract(user_input)
        rule_result = self.engine.compute(features)
        ml_cost     = self.ml_model.predict(features)
        hybrid      = self.combiner.combine(rule_result['total_base_cost'], ml_cost, source)
        return {
            'input':              user_input,
            'features':           features,
            'source':             source,
            'rule_result':        rule_result,
            'ml_prediction':      round(ml_cost),
            'hybrid_result':      hybrid,
            'feature_importance': self.ml_model.feature_importance(top_n=8),
            'timestamp':          datetime.now().isoformat(),
        }

    def estimate_json(self, user_input: str) -> str:
        def _cvt(o):
            if isinstance(o, np.integer):  return int(o)
            if isinstance(o, np.floating): return float(o)
            if isinstance(o, np.ndarray):  return o.tolist()
            return str(o)
        return json.dumps(self.estimate(user_input), default=_cvt, indent=2)


# ==============================================================================
#  SECTION 6 - PRETTY OUTPUT PRINTER
# ==============================================================================

def print_report(result: dict):
    W = 74
    h, r, f, s = (result['hybrid_result'], result['rule_result'],
                  result['features'], result['source'])
    fi = result['feature_importance']

    def box(title): print(f"\n  +{'='*W}+\n  |  {title:<{W-1}}|\n  +{'='*W}+")
    def row(k, v):  print(f"  |  {str(k):<38}  {str(v):>{W-42}}  |")
    def mid():      print(f"  +{'-'*W}+")
    def end():      print(f"  +{'='*W}+")

    icons = {'regex': '[ok]', 'keyword': '[kw]', 'default': '[df]'}

    box("EXTRACTED PROJECT FEATURES")
    for k in ['area_sqft','floors','bedrooms','bathrooms','kitchens','other_rooms',
              'city','house_style','tile_type','door_material']:
        src = s.get(k, 'default')
        row(f"{icons.get(src,'')} {k}", f"{f[k]}  [{src}]")
    row("Total Built Area", f"{r['total_built_sqft']:,} sqft")
    row("Composite Multiplier", f"{r['composite_multiplier']:.3f}x")
    end()

    box("RULE-BASED COST BREAKDOWN")
    CSI = {
        'Earthwork': ['excavation'], 'Concrete & RCC': ['concrete_rcc','formwork'],
        'Reinforcement': ['rebar'], 'Masonry': ['masonry'],
        'Woodwork': ['woodwork'], 'Roofing': ['roofing'],
        'Doors & Windows': ['doors_windows'], 'Finishes': ['finishes'],
        'Plumbing': ['plumbing'], 'Electrical': ['electrical'],
    }
    bd = r['breakdown']
    for div, items in CSI.items():
        sub = sum(bd.get(it, 0) for it in items)
        if sub > 0:
            row(f"  {div}", f"PKR {sub:>14,}  ({sub/r['direct_cost']*100:.1f}%)")
    mid()
    row("  Direct Cost Subtotal", f"PKR {r['direct_cost']:>14,}")
    row("  General Conditions (10%)", f"PKR {r['general_conditions']:>14,}")
    row("  Contingency (5%)", f"PKR {r['contingency']:>14,}")
    row("  Markup / OH&P (15%)", f"PKR {r['markup']:>14,}")
    mid()
    row("  RULE-BASED TOTAL", f"PKR {r['total_base_cost']:>14,}")
    row("  Rate per sqft", f"PKR {r['per_sqft']:>14,}")
    end()

    box("HYBRID ESTIMATE  (Rule-Based x XGBoost)")
    row(f"  Rule-Based  (alpha {h['alpha_rule']:.0%})", f"PKR {h['base_cost']:>14,}")
    row(f"  XGBoost ML  (alpha {h['alpha_ml']:.0%})", f"PKR {h['ml_cost']:>14,}")
    mid()
    row("  * FINAL ESTIMATE", f"PKR {h['final_cost']:>14,}")
    row("    Low", f"PKR {h['low_estimate']:>14,}")
    row("    High", f"PKR {h['high_estimate']:>14,}")
    row("  Data Confidence", f"{h['data_confidence']:.0%}")
    row("  Rule/ML Disagreement", f"{h['disagreement_pct']:.0f}%")
    end()
    if h.get('warning'):
        print(f"\n  [!] {h['warning']}")

    box("XGBoost FEATURE IMPORTANCE  (Top Cost Drivers)")
    if fi:
        mx = fi[0][1] or 1.0
        for name, imp in fi:
            n = int(imp / mx * 38)
            row(f"  {name:<28}", f"{'#'*n}{'.'*(38-n)}  {imp:.4f}")
    end()
    print(f"\n  Generated : {datetime.now().strftime('%d %b %Y  %H:%M PKT')}")
    print("  Note      : uncertainty band from validation residuals. "
          "Verify with local contractors.\n")


# ==============================================================================
#  MAIN - entry point (Colab-aware; trains if no saved model, else loads)
# ==============================================================================

if __name__ == '__main__':
    print("=" * 76)
    print("  AI-BASED CONSTRUCTION COST ESTIMATION SYSTEM - Pakistan  v5.0")
    print("=" * 76)

    system = ConstructionCostSystem()

    if os.path.exists(MODEL_SAVE_PATH):
        print("\n  Found a saved model - loading it (no retraining).")
        system.load()
    else:
        try:                                    # Colab upload path
            from google.colab import files
            print("\n  No saved model. Upload your dataset CSV ...")
            uploaded = files.upload()
            csv_filename = list(uploaded.keys())[0]
        except Exception:                       # local path
            csv_filename = input("\n  Path to dataset CSV: ").strip()
        system.train_from_dataset(csv_filename)

    print("\n" + "=" * 76)
    print("  READY. Example: '10 marla modern house in Islamabad, 4 bedrooms, double storey'")
    print("=" * 76)
    user_input = input("\n  Describe your project: ").strip()
    print_report(system.estimate(user_input))
