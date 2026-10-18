#!/usr/bin/env python3
"""Render diverse, realistic app-UI screenshots with headless Google Chrome.

These are GENUINE screenshot-like images (text rasterised by a real browser
text engine) used as the "authentic" class of a training/eval corpus.

CLI:
    python backend/tools/forge/render_chrome.py --out DIR --count N --seed S --workers K

API:
    from backend.tools.forge.render_chrome import render_batch
    rows = render_batch(out_dir, n, seed, workers)

Output:
    DIR/chrome/<id>.png
    DIR/chrome_manifest.jsonl   (one JSON line per image; appended)

Fields per manifest line: id, path, family, font_family, theme, viewport [w, h]
(CSS px), scale, seed (the per-image seed, = base_seed*100003+index), plus
extras (index, base_seed, variant, base_fs, currency).

Everything is deterministic given (seed, index): each image draws all of its
random parameters from its own ``random.Random(seed*100003+index)``.
No network and no third-party libraries are needed (only Pillow for a sanity
check of the output, which is optional).
"""
from __future__ import annotations

import argparse
import colorsys
import concurrent.futures as cf
import datetime as _dt
import html as _html
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# ----------------------------------------------------------------------------
# Chrome plumbing
# ----------------------------------------------------------------------------

MAC_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
MAX_LONG_SIDE = 2600  # cap on the long side of the output PNG, in device px


def find_chrome() -> str:
    env = os.environ.get("CHROME_BIN")
    if env and os.path.exists(env):
        return env
    if os.path.exists(MAC_CHROME):
        return MAC_CHROME
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        p = shutil.which(name)
        if p:
            return p
    raise RuntimeError("Google Chrome not found (set CHROME_BIN)")


CHROME_FLAGS = [
    "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
    "--no-default-browser-check", "--disable-extensions", "--disable-sync",
    "--disable-background-networking", "--disable-component-update",
    "--disable-default-apps", "--mute-audio", "--metrics-recording-only",
    "--disable-breakpad", "--disable-crash-reporter", "--disable-dev-shm-usage",
    "--force-color-profile=srgb", "--disable-lcd-text",
]


def _run_chrome(chrome: str, user_dir: str, html_path: str, out_png: str, w: int, h: int,
                scale: int, timeout: float = 60.0) -> bool:
    cmd = [chrome, *CHROME_FLAGS, f"--user-data-dir={user_dir}", f"--window-size={w},{h}",
           f"--force-device-scale-factor={scale}", f"--screenshot={out_png}",
           "file://" + html_path]
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    try:
        p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except Exception:
            p.kill()
        p.wait()
    finally:
        # Chrome may leave helper processes alive; make sure they are gone.
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except Exception:
            pass
    return os.path.exists(out_png) and os.path.getsize(out_png) > 500


# ----------------------------------------------------------------------------
# Fonts (all verified to resolve on macOS Chrome with --verify-fonts)
# ----------------------------------------------------------------------------
# (label, css stack, sampling weight, bucket) ; bucket: sans / serif / mono
FONTS = [
    ("SF (system-ui)", 'system-ui,"Helvetica Neue",Arial,sans-serif', 9, "sans"),
    ("Helvetica Neue", '"Helvetica Neue",Helvetica,Arial,sans-serif', 6, "sans"),
    ("Helvetica", 'Helvetica,Arial,sans-serif', 3, "sans"),
    ("Arial", 'Arial,Helvetica,sans-serif', 5, "sans"),
    ("Verdana", 'Verdana,Geneva,sans-serif', 3, "sans"),
    ("Tahoma", 'Tahoma,Verdana,sans-serif', 3, "sans"),
    ("Trebuchet MS", '"Trebuchet MS",Helvetica,sans-serif', 3, "sans"),
    ("Georgia", 'Georgia,"Times New Roman",serif', 2, "serif"),
    ("Menlo", 'Menlo,Monaco,monospace', 1.5, "mono"),
    ("Avenir Next", '"Avenir Next",Avenir,"Helvetica Neue",sans-serif', 4, "sans"),
    ("Avenir", 'Avenir,"Avenir Next","Helvetica Neue",sans-serif', 2, "sans"),
    ("Gill Sans", '"Gill Sans",Optima,sans-serif', 2, "sans"),
    ("Optima", 'Optima,"Gill Sans",sans-serif', 2, "sans"),
    ("Futura", 'Futura,"Avenir Next",sans-serif', 2, "sans"),
    ("Palatino", 'Palatino,"Palatino Linotype",serif', 1.5, "serif"),
    ("Lucida Grande", '"Lucida Grande",Tahoma,sans-serif', 2, "sans"),
    ("Courier New", '"Courier New",Courier,monospace', 1, "mono"),
    ("Charter", 'Charter,Georgia,serif', 1, "serif"),
    ("Seravek", 'Seravek,"Helvetica Neue",sans-serif', 2, "sans"),
    ("Geneva", 'Geneva,Verdana,sans-serif', 1, "sans"),
    ("PT Sans", '"PT Sans","Helvetica Neue",sans-serif', 2, "sans"),
    ("Times New Roman", '"Times New Roman",Times,serif', 1, "serif"),
    ("Iowan Old Style", '"Iowan Old Style",Palatino,serif', 1, "serif"),
    ("Galvji", 'Galvji,"Helvetica Neue",sans-serif', 1, "sans"),
]
_FONT_LABEL_TO_STACK = {f[0]: f[1] for f in FONTS}


def verify_fonts(chrome: str | None = None) -> dict:
    """Probe which of FONTS really resolve in Chrome (canvas width differs from fallbacks)."""
    chrome = chrome or find_chrome()
    names = [f[0].replace(" (system-ui)", "") for f in FONTS]
    page = """<html><body><pre id=o></pre><script>
const c=document.createElement('canvas').getContext('2d');
const t='Hamburgefonstiv 0123456789 @gQy';
function w(f){c.font='24px '+f;return c.measureText(t).width}
const names=%s;let r={};
for(const f of names){
  if(f==='SF'){r[f]=w('system-ui,monospace')!=w('monospace');continue;}
  // an unresolved font falls back to the generic family given, so all three widths match;
  // a resolved font may coincide with at most one generic default (e.g. Menlo == monospace)
  let same=(w('"'+f+'",monospace')==w('monospace'))+(w('"'+f+'",serif')==w('serif'))+(w('"'+f+'",sans-serif')==w('sans-serif'));
  r[f]=same<=1;
}
document.getElementById('o').textContent=JSON.stringify(r);
</script></body></html>""" % json.dumps([n if n != "SF" else "SF" for n in names])
    tmp = tempfile.mkdtemp(prefix="fontprobe_")
    try:
        hp = os.path.join(tmp, "f.html")
        Path(hp).write_text(page)
        out = subprocess.run([chrome, *CHROME_FLAGS, f"--user-data-dir={tmp}/ud", "--dump-dom",
                              "file://" + hp], capture_output=True, text=True, timeout=60).stdout
        s = out[out.index('<pre id="o">') + 12: out.index("</pre>")]
        return json.loads(_html.unescape(s))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ----------------------------------------------------------------------------
# Data pools (no network, no faker)
# ----------------------------------------------------------------------------
FIRST = ["Aarav", "Priya", "Rohan", "Ananya", "Vikram", "Sneha", "Arjun", "Kavya", "Rahul", "Neha",
         "Siddharth", "Meera", "Karthik", "Divya", "Aditya", "Pooja", "Manish", "Ishita", "Rajesh",
         "Sunita", "Amit", "Deepa", "Nikhil", "Shruti", "Varun", "Anjali", "Harsh", "Tanvi", "Farhan",
         "Zoya", "Emma", "Liam", "Olivia", "Noah", "Sophia", "James", "Ava", "Lucas", "Mia", "Ethan",
         "Isabella", "Daniel", "Chloe", "Marcus", "Hannah", "Tyler", "Grace", "Omar", "Fatima", "Chen",
         "Yuki", "Mateo", "Lena", "Sven", "Aisha", "Diego", "Nora", "Jack", "Ruby", "Leo", "Maya"]
LAST = ["Sharma", "Patel", "Iyer", "Reddy", "Nair", "Gupta", "Singh", "Menon", "Kapoor", "Joshi",
        "Verma", "Das", "Bose", "Rao", "Khan", "Mehta", "Pillai", "Chopra", "Banerjee", "Agarwal",
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Martinez",
        "Wilson", "Anderson", "Taylor", "Thomas", "Moore", "Clark", "Lewis", "Walker", "Hall",
        "Young", "Allen", "Wright", "King", "Scott", "Green", "Baker", "Adams", "Nelson", "Carter"]
MERCH_IN = ["Swiggy", "Zomato", "Amazon Pay", "Flipkart", "BigBasket", "Reliance Fresh", "Uber India",
            "Ola Cabs", "IRCTC", "Myntra", "Airtel Prepaid", "Jio Recharge", "BookMyShow",
            "Apollo Pharmacy", "DMart", "Starbucks", "Cafe Coffee Day", "Indian Oil Petrol", "Netflix",
            "Spotify", "Blinkit", "Zepto", "MakeMyTrip", "Decathlon", "Croma", "Haldiram's", "Nykaa",
            "Domino's Pizza", "Tata Power", "BESCOM Electricity", "Lenskart", "PharmEasy"]
MERCH_US = ["Walmart", "Target", "Amazon.com", "Uber Trip", "Starbucks", "Whole Foods Market", "Netflix",
            "Shell Oil", "Costco Wholesale", "Apple Store", "Spotify USA", "Chipotle", "Lyft Ride",
            "CVS Pharmacy", "Delta Air Lines", "DoorDash", "Trader Joe's", "Home Depot", "Best Buy",
            "Airbnb", "Steam Games", "Walgreens", "IKEA", "Tesco", "Sainsbury's", "Boots", "Zara"]
BANKS_IN = ["HDFC Bank", "State Bank of India", "ICICI Bank", "Axis Bank", "Kotak Mahindra Bank",
            "Punjab National Bank", "Bank of Baroda", "Canara Bank", "IDFC FIRST Bank", "Yes Bank"]
BANKS_US = ["Chase", "Bank of America", "Wells Fargo", "Citibank", "Capital One", "Barclays", "Revolut",
            "Monzo", "HSBC", "Ally Bank", "TD Bank", "US Bank"]
UPI_SUFFIX = ["oksbi", "ybl", "paytm", "okaxis", "okhdfcbank", "upi", "icici", "axl", "ibl"]
COINS = [("Bitcoin", "BTC", 64000, "#f7931a"), ("Ethereum", "ETH", 3300, "#627eea"),
         ("Solana", "SOL", 150, "#14f195"), ("Tether", "USDT", 1, "#26a17b"),
         ("BNB", "BNB", 580, "#f3ba2f"), ("XRP", "XRP", 0.55, "#23292f"),
         ("Dogecoin", "DOGE", 0.15, "#c2a633"), ("Cardano", "ADA", 0.45, "#0033ad"),
         ("Polygon", "MATIC", 0.7, "#8247e5"), ("Avalanche", "AVAX", 35, "#e84142"),
         ("Chainlink", "LINK", 14, "#2a5ada"), ("Litecoin", "LTC", 80, "#345d9d"),
         ("Polkadot", "DOT", 7, "#e6007a"), ("Shiba Inu", "SHIB", 0.000025, "#ffa409")]
STOCKS_IN = [("RELIANCE", 2900), ("TCS", 3900), ("INFY", 1500), ("HDFCBANK", 1650), ("ITC", 430),
             ("SBIN", 780), ("TATAMOTORS", 950), ("WIPRO", 480), ("BHARTIARTL", 1250),
             ("ADANIPORTS", 1300), ("LT", 3500), ("MARUTI", 12000), ("ZOMATO", 220), ("PAYTM", 450)]
STOCKS_US = [("AAPL", 190), ("MSFT", 410), ("GOOGL", 150), ("AMZN", 180), ("TSLA", 210),
             ("NVDA", 880), ("META", 490), ("NFLX", 600), ("AMD", 160), ("DIS", 110),
             ("JPM", 190), ("KO", 60), ("V", 280), ("PYPL", 62)]
PRODUCTS = [("Wireless Earbuds Pro", "🎧", 4999), ("Running Shoes - Blue", "👟", 3499),
            ("Cotton T-Shirt (Pack of 2)", "👕", 899), ("Smart Watch Series 5", "⌚", 8999),
            ("Stainless Steel Bottle 1L", "🍶", 599), ("Laptop Backpack 30L", "🎒", 1799),
            ("USB-C Fast Charger 65W", "🔌", 1299), ("Bluetooth Speaker Mini", "🔊", 2199),
            ("Hardcover Notebook A5", "📓", 349), ("Desk Lamp LED", "💡", 1099),
            ("Yoga Mat 6mm", "🧘", 799), ("Coffee Beans 500g", "☕", 650), ("Sunglasses UV400", "🕶️", 1499),
            ("Mechanical Keyboard", "⌨️", 5499), ("Phone Case - Clear", "📱", 399),
            ("Face Wash 150ml", "🧴", 249), ("Table Tennis Racket", "🏓", 1299), ("Protein Powder 1kg", "💪", 2399)]
FOODS = [("Chicken Biryani", 280), ("Paneer Butter Masala", 240), ("Margherita Pizza", 349), ("Veg Burger", 159),
         ("Masala Dosa", 120), ("Butter Naan x2", 80), ("Cold Coffee", 140), ("Pad Thai", 320),
         ("Caesar Salad", 260), ("Fish Tacos", 310), ("Chocolate Brownie", 130), ("Pasta Alfredo", 290),
         ("Sushi Platter", 640), ("Falafel Wrap", 190), ("Fries (Large)", 110), ("Mango Lassi", 99)]
PLACES = ["Indiranagar", "Koramangala", "Connaught Place", "Bandra West", "HSR Layout", "Whitefield",
          "Anna Nagar", "Salt Lake", "Banjara Hills", "T. Nagar", "Downtown", "Midtown", "Brooklyn Heights",
          "Shoreditch", "King's Cross", "Airport Terminal 2", "Central Station", "City Mall", "Tech Park",
          "Lakeview Apartments", "Sector 21", "MG Road", "Marine Drive", "Park Street"]
SOCIAL_BODIES = [
    "Just shipped the new feature after three weeks of late nights. Feels incredible!",
    "Coffee first, emails later. That's the whole productivity system.",
    "Hot take: most meetings should be a two-line message.",
    "Reached the summit at sunrise today. Totally worth the 4am alarm.",
    "Anyone else think the new update made everything slower? Just me?",
    "Finished my first marathon in 4:12. Legs are gone but the heart is full.",
    "Reminder to hydrate, stretch, and touch some grass today.",
    "We are hiring! Looking for two backend engineers who love messy problems. DM me.",
    "The best code review comment I ever got: 'delete this'. It was right.",
    "Spent the weekend learning to bake sourdough. Result: one very dense brick.",
    "Can't believe the match last night. What a finish! Still shaking.",
    "New blog post is live: what I learned from running a side project for five years.",
    "Traffic today was unreal. Took 2 hours for 9 km. Work from home forever.",
    "Thank you all for 10K followers. You are the best community on this app.",
    "Flight delayed again. At this point the airport sandwich knows me by name.",
]
EMAIL_SUBJECTS = [
    ("Your order has shipped", "Your package is on its way and should arrive by"),
    ("Security alert: new sign-in", "We noticed a new sign-in to your account from a"),
    ("Invoice #{n} from {co}", "Please find attached your invoice for the period"),
    ("Your monthly statement is ready", "Your account statement for the month of"),
    ("Meeting moved to 3 PM", "Hi team, quick update - the sync has been moved"),
    ("Welcome to {co}!", "Thanks for signing up. Here is how to get started with"),
    ("Payment received - thank you", "We have received your payment of the amount"),
    ("Your OTP for login", "Use the one-time password below to complete your"),
    ("Flight confirmation {n}", "Your booking is confirmed. Check-in opens 48 hours"),
    ("Re: project proposal draft", "Thanks for sending this over, I had a look and"),
    ("Weekly digest: top stories", "Here are the most read stories from your network this"),
    ("Action required: verify your email", "Please confirm your email address to keep your"),
    ("Your subscription renews soon", "This is a reminder that your plan will renew on"),
    ("Receipt for your payment", "Thank you for your purchase. Your receipt is below"),
    ("Interview schedule for Friday", "Hope you are doing well. We would like to schedule"),
]
COMPANIES = ["Acme Corp", "Globex", "Initech", "Umbrella Labs", "Stark Industries", "Wayne Tech", "Hooli",
             "Soylent", "Cyberdyne", "Vandelay Imports", "Pied Piper", "Aperture Science", "Massive Dynamic",
             "Nimbus Cloud", "BlueRiver Logistics", "Orbit Analytics", "Lumen Health", "Quartz Finance"]
APPS_N = [("WhatsApp", "#25d366"), ("Messages", "#34c759"), ("Gmail", "#ea4335"), ("Instagram", "#c13584"),
          ("PhonePe", "#5f259f"), ("Google Pay", "#4285f4"), ("Paytm", "#00baf2"), ("Slack", "#4a154b"),
          ("Swiggy", "#fc8019"), ("Uber", "#111111"), ("Calendar", "#ea4335"), ("Amazon", "#ff9900"),
          ("HDFC Bank", "#004c8f"), ("Telegram", "#2aabee"), ("X", "#000000"), ("Spotify", "#1db954")]
CITIES = ["Mumbai", "Delhi", "Bengaluru", "Chennai", "Kolkata", "Pune", "Hyderabad", "London", "New York",
          "Austin", "Berlin", "Toronto", "Dubai", "Singapore"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

CURRENCIES = [
    # code, symbol, indian-grouping, weight, region
    {"code": "INR", "sym": "₹", "alt": "Rs.", "indian": True, "w": 46, "region": "in"},
    {"code": "USD", "sym": "$", "alt": "$", "indian": False, "w": 30, "region": "us"},
    {"code": "EUR", "sym": "€", "alt": "€", "indian": False, "w": 8, "region": "us"},
    {"code": "GBP", "sym": "£", "alt": "£", "indian": False, "w": 8, "region": "us"},
    {"code": "AED", "sym": "AED ", "alt": "AED ", "indian": False, "w": 4, "region": "us"},
    {"code": "SGD", "sym": "S$", "alt": "S$", "indian": False, "w": 4, "region": "us"},
]

# ----------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------
esc = lambda s: _html.escape(str(s), quote=True)


def wchoice(r: random.Random, items, weights):
    return r.choices(items, weights=weights, k=1)[0]


def hsl(h, s, l, a=None):
    if a is None:
        return f"hsl({h:.0f} {s:.0f}% {l:.0f}%)"
    return f"hsl({h:.0f} {s:.0f}% {l:.0f}% / {a})"


def group_digits(n: int, indian: bool) -> str:
    s = str(n)
    if len(s) <= 3:
        return s
    if not indian:
        return f"{n:,}"
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts) + "," + tail


SVG_ICONS = {
    "back": "M15 5l-7 7 7 7", "chev": "M9 5l7 7-7 7", "down": "M5 9l7 7 7-7",
    "home": "M4 11l8-7 8 7v9h-5v-6h-6v6H4z",
    "search": "M11 4a7 7 0 100 14 7 7 0 000-14zM20 20l-4.5-4.5",
    "user": "M12 4a4 4 0 100 8 4 4 0 000-8zM4 21c0-4 4-6 8-6s8 2 8 6",
    "bell": "M6 17v-6a6 6 0 1112 0v6l2 2H4zM10 21h4",
    "card": "M3 6h18v12H3zM3 10h18", "chart": "M5 20V11M11 20V4M17 20v-6M3 20h18",
    "send": "M3 11l18-8-8 18-2-8z", "dots": "M5 12h.01M12 12h.01M19 12h.01",
    "vdots": "M12 5h.01M12 12h.01M12 19h.01",
    "check": "M5 12.5l5 5L19 7", "plus": "M12 5v14M5 12h14", "close": "M6 6l12 12M18 6L6 18",
    "heart": "M12 20s-8-5-8-11a4.5 4.5 0 018-3 4.5 4.5 0 018 3c0 6-8 11-8 11z",
    "reply": "M10 6L4 12l6 6M4 12h10a6 6 0 016 6",
    "repost": "M4 9l4-4 4 4M8 5v9a3 3 0 003 3h4M20 15l-4 4-4-4M16 19v-9a3 3 0 00-3-3H9",
    "share": "M12 3v12M7 8l5-5 5 5M5 14v6h14v-6", "star": "M12 3l2.8 5.9 6.2.8-4.6 4.3 1.2 6.3-5.6-3.1-5.6 3.1 1.2-6.3L3 9.7l6.2-.8z",
    "menu": "M4 7h16M4 12h16M4 17h16", "phone": "M5 4h4l2 5-3 2a11 11 0 005 5l2-3 5 2v4a2 2 0 01-2 2A16 16 0 013 6a2 2 0 012-2z",
    "video": "M3 7h12v10H3zM15 11l6-3v8l-6-3", "mic": "M12 3a3 3 0 013 3v6a3 3 0 01-6 0V6a3 3 0 013-3zM6 11a6 6 0 0012 0M12 17v4",
    "clip": "M20 11l-8 8a5 5 0 01-7-7l9-9a3.5 3.5 0 015 5l-9 9a2 2 0 01-3-3l8-8",
    "camera": "M3 8h4l2-3h6l2 3h4v12H3zM12 11a3.5 3.5 0 100 7 3.5 3.5 0 000-7z",
    "up": "M12 19V5M5 12l7-7 7 7", "downarrow": "M12 5v14M5 12l7 7 7-7", "swap": "M7 4L3 8l4 4M3 8h14M17 20l4-4-4-4M21 16H7",
    "cart": "M3 4h3l2 12h11l2-8H7M10 20h.01M18 20h.01", "wallet": "M3 7h16a2 2 0 012 2v10H3zM3 7V5h14v2M16 14h.01",
    "qr": "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h3v3M20 14v6M14 20h3", "gear": "M12 9a3 3 0 100 6 3 3 0 000-6zM12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2 2M16.4 16.4l2 2M5.6 18.4l2-2M16.4 7.6l2-2",
    "mail": "M3 6h18v12H3zM3 7l9 7 9-7", "pin": "M12 21s7-6 7-11a7 7 0 10-14 0c0 5 7 11 7 11zM12 7.5a2.5 2.5 0 100 5 2.5 2.5 0 000-5z",
    "trash": "M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13", "pencil": "M4 20l1-5L16 4l4 4L9 19z",
    "bookmark": "M6 3h12v18l-6-5-6 5z", "file": "M6 3h8l4 4v14H6zM14 3v4h4", "globe": "M12 3a9 9 0 100 18 9 9 0 000-18zM3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18",
    "lock": "M6 11h12v9H6zM8 11V8a4 4 0 118 0v3", "grid": "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z",
    "refresh": "M20 12a8 8 0 10-3 6.2M20 5v7h-7", "download": "M12 4v12M7 11l5 5 5-5M5 20h14",
}


def ico(name: str, size: float = 1.3, color: str = "currentColor", sw: float = 2.0, fill: str = "none") -> str:
    d = SVG_ICONS[name]
    cap = ' stroke-linecap="round"' if name in ("dots", "vdots") else ' stroke-linecap="round"'
    if name in ("dots", "vdots"):
        sw = 3.4
    return (f'<svg class="ic" viewBox="0 0 24 24" width="{size}em" height="{size}em" fill="{fill}" '
            f'stroke="{color}" stroke-width="{sw}"{cap} stroke-linejoin="round"><path d="{d}"/></svg>')


def spark(r: random.Random, up: bool, w=64, h=24, color="#16a34a", n=14) -> str:
    v, pts = 0.0, []
    for i in range(n):
        v += r.uniform(-1, 1) + (0.35 if up else -0.35)
        pts.append(v)
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or 1
    xy = " ".join(f"{i * w / (n - 1):.1f},{h - 2 - (p - lo) / span * (h - 4):.1f}" for i, p in enumerate(pts))
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" width="{w}" height="{h}" style="flex:none"><polyline points="{xy}" '
            f'fill="none" stroke="{color}" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/></svg>')


class Ctx:
    """Per-image random parameters + convenience formatters."""

    def __init__(self, rng: random.Random, W: int, H: int, mobile: bool, family: str):
        self.r = rng
        self.W, self.H, self.mobile, self.family = W, H, mobile, family
        self.vars: dict[str, str] = {}
        self.sb_bg = "var(--bg)"
        self.sb_fg = "var(--fg)"
        self.tabbar = False
        self.cur = wchoice(rng, CURRENCIES, [c["w"] for c in CURRENCIES])
        self.use_alt = rng.random() < 0.35 and self.cur["code"] == "INR"
        self.region = self.cur["region"]
        self.variant = ""

    # --- formatting -------------------------------------------------------
    def money(self, x: float, dec: bool | None = None, sign: bool = False, abs_: bool = False, nosym: bool = False) -> str:
        if dec is None:
            dec = True
        neg = x < 0
        x = abs(x)
        if dec:
            whole = int(x)
            frac = int(round((x - whole) * 100))
            if frac == 100:
                whole, frac = whole + 1, 0
            num = group_digits(whole, self.cur["indian"]) + f".{frac:02d}"
        else:
            num = group_digits(int(round(x)), self.cur["indian"])
        sym = "" if nosym else (self.cur["alt"] if self.use_alt else self.cur["sym"])
        pre = "-" if neg and not abs_ else ("+" if sign and not neg else "")
        return f"{pre}{sym}{num}"

    def amount(self, lo: float, hi: float) -> float:
        # amounts roughly log-uniform, scaled by currency
        k = 1.0 if self.cur["code"] == "INR" else 0.045
        v = lo * k * (hi / lo) ** self.r.random()
        if self.cur["code"] == "INR" and v > 100:
            v = round(v) if self.r.random() < 0.7 else round(v, 2)
        return round(max(v, 1), 2)

    def merchant(self) -> str:
        return self.r.choice(MERCH_IN if self.region == "in" else MERCH_US + (MERCH_IN[:6] if self.r.random() < .1 else []))

    def bank(self) -> str:
        return self.r.choice(BANKS_IN if self.region == "in" else BANKS_US)

    def person(self) -> str:
        r = self.r
        return f"{r.choice(FIRST)} {r.choice(LAST)}"

    def date(self, back_days: int = 400, fmt: str | None = None):
        r = self.r
        d = _dt.date(2025, 11, 20) - _dt.timedelta(days=r.randint(0, back_days))
        return d if fmt is None else self.fmt_date(d, fmt)

    def fmt_date(self, d, fmt: str | None = None) -> str:
        r = self.r
        fmt = fmt or r.choice(["dmy_mon", "mon_dmy", "num", "dash", "long"])
        if fmt == "dmy_mon":
            return f"{d.day} {MONTHS[d.month - 1]} {d.year}"
        if fmt == "mon_dmy":
            return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"
        if fmt == "num":
            return f"{d.day:02d}/{d.month:02d}/{d.year}"
        if fmt == "dash":
            return f"{d.day:02d}-{d.month:02d}-{d.year}"
        if fmt == "short":
            return f"{d.day} {MONTHS[d.month - 1]}"
        if fmt == "yy":
            return f"{d.day:02d}/{d.month:02d}/{d.year % 100:02d}"
        if fmt == "wk":
            return f"{DAYS[d.weekday()]}, {d.day} {MONTHS[d.month - 1]}"
        return f"{DAYS[d.weekday()]}, {MONTHS[d.month - 1]} {d.day}, {d.year}"

    def time(self, h24: bool | None = None, hh=None, mm=None) -> str:
        r = self.r
        hh = r.randint(0, 23) if hh is None else hh
        mm = r.randint(0, 59) if mm is None else mm
        if h24 is None:
            h24 = getattr(self, "_h24", None)
            if h24 is None:
                h24 = self._h24 = r.random() < 0.3
        if h24:
            return f"{hh:02d}:{mm:02d}"
        ap = "AM" if hh < 12 else "PM"
        if r.random() < 0.15 and getattr(self, "_lc_ap", None) is None:
            self._lc_ap = True
        if getattr(self, "_lc_ap", False):
            ap = ap.lower()
        return f"{(hh % 12) or 12}:{mm:02d} {ap}"

    def digits(self, n: int) -> str:
        r = self.r
        return str(r.randint(1, 9)) + "".join(str(r.randint(0, 9)) for _ in range(n - 1))

    def alnum(self, n: int, prefix: str = "") -> str:
        r = self.r
        al = "ABCDEFGHJKLMNPQRSTUVWXYZ0123456789"
        return prefix + "".join(r.choice(al) for _ in range(n))

    def upi_id(self, name: str | None = None) -> str:
        r = self.r
        nm = (name or self.person()).lower().replace(" ", r.choice([".", "", "_"]))
        if r.random() < 0.3:
            nm = self.digits(10)
        return f"{nm}@{r.choice(UPI_SUFFIX)}"

    def n_rows(self, em_per_row: float, extra: int = 3) -> int:
        return max(4, int(self.H / (self.fs * em_per_row)) + extra)

    @property
    def fs(self) -> float:
        return float(self.vars.get("--fs", "16px").replace("px", ""))


def avatar(c: Ctx, name: str, size: float = 2.6, shape: str = "circle", bg: str | None = None, fs: float = 1.0) -> str:
    """Initial-letter avatar; colour is derived from the name."""
    h = sum(ord(ch) * (i + 3) for i, ch in enumerate(name)) % 360
    bg = bg or f"linear-gradient(135deg,hsl({h} 60% 52%),hsl({(h + 40) % 360} 65% 42%))"
    rad = "50%" if shape == "circle" else ("28%" if shape == "squircle" else "6px")
    ini = (name.strip()[:1] or "?").upper()
    return (f'<div class="av" style="width:{size}em;height:{size}em;border-radius:{rad};background:{bg};'
            f'font-size:{fs}em"><span style="font-size:{size * 0.45:.2f}em">{esc(ini)}</span></div>')


def app_icon(label: str, color: str, size: float = 2.2) -> str:
    return (f'<div class="av" style="width:{size}em;height:{size}em;border-radius:24%;background:{color};'
            f'flex:none"><span style="font-size:{size * 0.5:.2f}em">{esc(label[:1])}</span></div>')


# ----------------------------------------------------------------------------
# Theme + base CSS
# ----------------------------------------------------------------------------
BASE_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:var(--W);height:var(--H);overflow:hidden;background:var(--bg)}
body{font-family:var(--ff);font-size:var(--fs);font-weight:var(--fw);color:var(--fg);line-height:var(--lh);
 letter-spacing:var(--ls);-webkit-text-size-adjust:none;text-rendering:optimizeLegibility}
b,strong,.b{font-weight:var(--fwb)}
.screen{position:relative;width:var(--W);height:var(--H);display:flex;flex-direction:column;overflow:hidden;background:var(--bg)}
.sb{flex:none;display:flex;align-items:center;justify-content:space-between;padding:0 24px;height:var(--sbh);
 font:600 15px/1 system-ui,"Helvetica Neue",Arial,sans-serif;letter-spacing:0;position:relative;z-index:5}
.sb .l,.sb .rr{display:flex;align-items:center;gap:6px;min-width:0}
.sb .isl{position:absolute;left:50%;top:11px;width:112px;height:32px;margin-left:-56px;background:#000;border-radius:20px}
.sig{display:inline-flex;align-items:flex-end;gap:2px;height:12px}
.sig i{display:block;width:3.5px;background:currentColor;border-radius:1px}
.bat{display:inline-block;position:relative;width:25px;height:12px;border:1.5px solid currentColor;border-radius:4px;opacity:.92}
.bat i{position:absolute;left:1.5px;top:1.5px;bottom:1.5px;background:currentColor;border-radius:2px}
.bat:after{content:"";position:absolute;right:-4px;top:3px;width:2px;height:4px;background:currentColor;border-radius:0 2px 2px 0}
.app{flex:1;min-height:0;overflow:hidden;position:relative;display:flex;flex-direction:column}
.tabbar{flex:none;display:flex;justify-content:space-around;align-items:flex-start;padding:.55em .3em 0;
 height:var(--tbh);background:var(--bar);border-top:1px solid var(--line);position:relative}
.tabbar .t{display:flex;flex-direction:column;align-items:center;gap:.15em;font-size:.68em;color:var(--fg2);min-width:0}
.tabbar .t.on{color:var(--accent-t)}
.tabbar .t .ic{width:1.9em;height:1.9em}
.home{position:absolute;left:50%;bottom:7px;width:34%;height:5px;margin-left:-17%;border-radius:3px;background:var(--fg);opacity:.85}
.row{display:flex;align-items:center}.col{display:flex;flex-direction:column}
.g1{gap:.45em}.g2{gap:.9em}.g3{gap:1.4em}.grow{flex:1;min-width:0}.none{flex:none}
.mu{color:var(--fg2)}.sm{font-size:.84em}.xs{font-size:.7em}.lg{font-size:1.2em}.nw{white-space:nowrap}
.ell{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.r{text-align:right}.ctr{text-align:center}.wrap{overflow-wrap:anywhere}
.card{background:var(--card);border-radius:var(--r);box-shadow:var(--sh);padding:1em;border:var(--cb)}
.hr{border-top:1px solid var(--line)}
.av{display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;flex:none;overflow:hidden;line-height:1}
.pill{display:inline-flex;align-items:center;gap:.3em;border-radius:99px;padding:.18em .7em;font-size:.76em;font-weight:600;white-space:nowrap}
.btn{display:flex;align-items:center;justify-content:center;gap:.4em;border-radius:var(--rb);padding:.8em 1em;
 background:var(--accent);color:var(--accent-fg);font-weight:var(--fwb);text-align:center}
.btn.o{background:transparent;color:var(--accent-t);border:1.5px solid var(--accent)}
.good{color:var(--good)}.bad{color:var(--bad)}
.ic{flex:none;display:block}
.hdr{flex:none;display:flex;align-items:center;gap:.8em;padding:.7em 1em;background:var(--bar);position:relative;z-index:2}
.sect{font-size:.78em;font-weight:var(--fwb);text-transform:uppercase;letter-spacing:.06em;color:var(--fg2);padding:1em 1em .4em}
.li{display:flex;align-items:center;gap:.85em;padding:.8em 1em;position:relative}
.li+.li:before{content:"";position:absolute;left:var(--divl,1em);right:0;top:0;border-top:1px solid var(--line)}
.tbl{width:100%;border-collapse:collapse}
.tbl th{font-weight:var(--fwb);text-align:left;font-size:.82em;color:var(--fg2);padding:.6em .5em;border-bottom:2px solid var(--line);white-space:nowrap}
.tbl td{padding:.62em .5em;border-bottom:1px solid var(--line);vertical-align:middle}
.tbl .n{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.chk{display:inline-flex;align-items:center;justify-content:center;border-radius:50%;flex:none}
.bwin{display:flex;flex-direction:column;width:var(--W);height:var(--H);background:var(--bg)}
.btop{flex:none;display:flex;align-items:flex-end;gap:12px;padding:10px 14px 0;background:var(--chrome1);font:12px/1 system-ui,"Helvetica Neue",Arial,sans-serif;color:var(--chromefg)}
.btop .dots{display:flex;gap:7px;padding-bottom:12px}.btop .dots i{width:12px;height:12px;border-radius:50%;display:block}
.btab{padding:8px 14px;border-radius:9px 9px 0 0;background:var(--chrome2);min-width:180px;max-width:240px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bbar{flex:none;display:flex;align-items:center;gap:12px;padding:7px 14px;background:var(--chrome2);color:var(--chromefg);border-bottom:1px solid var(--line);font:13px/1 system-ui,"Helvetica Neue",Arial,sans-serif}
.url{flex:1;background:var(--chrome1);border-radius:99px;padding:7px 14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bpage{flex:1;min-height:0;overflow:hidden;position:relative;font-family:var(--ff);font-size:var(--fs);color:var(--fg);background:var(--bg)}
.web{max-width:var(--colw);margin:0 auto;height:100%;display:flex;flex-direction:column;background:var(--bg);overflow:hidden;position:relative}
"""

LIGHT_BG = [("#ffffff", "#f2f2f7", "#ffffff"), ("#f2f2f7", "#f2f2f7", "#ffffff"), ("#f5f6fa", "#e9ecf3", "#ffffff"),
            ("#fafafa", "#f0f0f0", "#ffffff"), ("#eef1f5", "#e2e7ee", "#ffffff"), ("#fdf8f2", "#f4ece1", "#fffdfa"),
            ("#f4f7f6", "#e3ebe8", "#ffffff"), ("#fff", "#f6f6f6", "#fbfbfb")]
DARK_BG = [("#000000", "#1c1c1e", "#1c1c1e"), ("#0b0f14", "#161c24", "#141a22"), ("#121212", "#1e1e1e", "#1e1e1e"),
           ("#1c1c1e", "#2c2c2e", "#2c2c2e"), ("#0f172a", "#1e293b", "#1b2538"), ("#17212b", "#232e3c", "#1f2a37"),
           ("#0d1117", "#161b22", "#161b22"), ("#191919", "#262626", "#222222")]


def make_theme(c: Ctx, dark: bool) -> None:
    r = c.r
    h = r.uniform(0, 360)
    if r.random() < 0.55:  # favour familiar hues: blue/green/purple/orange/red
        h = r.choice([210, 217, 142, 152, 262, 280, 24, 12, 340, 175, 195, 45]) + r.uniform(-8, 8)
    s = r.uniform(55, 88)
    l = r.uniform(40, 50) if not dark else r.uniform(48, 58)
    accent = hsl(h, s, l)
    accent_t = hsl(h, s, l if not dark else min(l + 12, 70)) if not dark else hsl(h, min(s + 5, 95), 68)
    if not dark:
        accent_t = hsl(h, s, max(l - 6, 30))
    bg, bg2, card = r.choice(DARK_BG if dark else LIGHT_BG)
    fg = r.choice(["#ffffff", "#f1f1f3", "#e6e9ee"]) if dark else r.choice(["#000000", "#111111", "#1c1c1e", "#0f172a", "#202124"])
    fg2 = "rgba(235,235,245,.62)" if dark else r.choice(["rgba(60,60,67,.62)", "#6b7280", "#667085", "#5f6368"])
    line = "rgba(255,255,255,.12)" if dark else r.choice(["rgba(0,0,0,.09)", "#e5e7eb", "rgba(60,60,67,.14)"])
    shadow_style = r.choice(["none", "soft", "soft", "strong", "border"])
    sh = {"none": "none", "soft": "0 1px 3px rgba(0,0,0,.10),0 4px 14px rgba(0,0,0,.06)" if not dark else "0 1px 3px rgba(0,0,0,.5)",
          "strong": "0 6px 22px rgba(0,0,0,.16)" if not dark else "0 8px 24px rgba(0,0,0,.6)",
          "border": "none"}[shadow_style]
    cb = f"1px solid {line}" if shadow_style in ("border", "none") else "none"
    rad = r.choice([0, 4, 8, 10, 12, 14, 16, 20, 24])
    bar = card if r.random() < 0.6 else bg
    if dark and bar == "#000000":
        bar = "#000000"
    c.dark = dark
    c.hue = h
    v = c.vars
    v.update({
        "--bg": bg, "--bg2": bg2, "--card": card, "--bar": bar, "--fg": fg, "--fg2": fg2, "--line": line,
        "--accent": accent, "--accent-t": accent_t, "--accent-fg": "#ffffff", "--sh": sh, "--cb": cb,
        "--r": f"{rad}px", "--rb": f"{r.choice([6, 10, 12, 99, 99, 14, 4])}px",
        "--good": "#30d158" if dark else r.choice(["#16a34a", "#0f9d58", "#1a7f37", "#2e7d32"]),
        "--bad": "#ff6961" if dark else r.choice(["#dc2626", "#d93025", "#c62828", "#e5484d"]),
        "--chrome1": "#202124" if dark else "#dee1e6", "--chrome2": "#35363a" if dark else "#ffffff",
        "--chromefg": "#e8eaed" if dark else "#3c4043",
    })
    c.accent, c.accent_t = accent, accent_t
    c.good, c.bad = v["--good"], v["--bad"]


def pick_font(r: random.Random):
    return wchoice(r, FONTS, [f[2] for f in FONTS])


def hero_gradient(c: Ctx, dark: bool | None = None) -> str:
    r = c.r
    h1 = c.hue + r.uniform(-25, 25)
    h2 = h1 + r.choice([20, 35, 50, -30, -45, 70])
    l1 = r.uniform(32, 46)
    kind = r.choice(["linear", "linear", "radial", "solid"])
    a = hsl(h1, r.uniform(60, 85), l1)
    b = hsl(h2, r.uniform(60, 85), l1 + r.uniform(-8, 10))
    if kind == "solid":
        return a
    if kind == "radial":
        return f"radial-gradient(circle at {r.choice([10, 30, 80])}% 0%,{b},{a})"
    return f"linear-gradient({r.choice([120, 135, 160, 180, 90])}deg,{a},{b})"


# ----------------------------------------------------------------------------
# Chrome pieces: status bar, tab bar, browser frame
# ----------------------------------------------------------------------------

def status_bar(c: Ctx) -> str:
    r = c.r
    kind = c.sb_kind
    t = c.time(h24=kind == "android" or r.random() < 0.15, hh=r.randint(0, 23), mm=r.randint(0, 59))
    t = t.replace(" AM", "").replace(" PM", "").replace(" am", "").replace(" pm", "")
    net = r.choice(["5G", "LTE", "4G", "5G", "", ""])
    pct = r.randint(8, 100)
    bars = "".join(f'<i style="height:{3 + k * 2.6:.1f}px;opacity:{1 if k < r.randint(2, 4) else .35}"></i>' for k in range(4))
    batt = f'<span class="bat"><i style="width:{max(pct * 0.22, 3):.1f}px"></i></span>'
    pct_txt = f'<span style="font-size:13px;font-weight:600">{pct}%</span>' if (kind == "android" or r.random() < 0.2) else ""
    wifi = f'<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"><path d="M2 9a14 14 0 0120 0M5.5 13a9 9 0 0113 0M9 17a4 4 0 016 0"/></svg>'
    isl = '<div class="isl"></div>' if c.sb_island else ""
    left = f'<span class="l"><span>{t}</span></span>'
    right = f'<span class="rr">{"<span style=font-size:13px>" + net + "</span>" if net else ""}<span class="sig">{bars}</span>{wifi if r.random() < .6 else ""}{pct_txt}{batt}</span>'
    if kind == "android":
        left = f'<span class="l"><span>{t}</span></span>'
    return f'<div class="sb" style="background:{c.sb_bg};color:{c.sb_fg}">{isl}{left}{right}</div>'


def tab_bar(c: Ctx, labels: list[tuple[str, str]], on: int) -> str:
    items = []
    for i, (ic, lab) in enumerate(labels):
        items.append(f'<div class="t{" on" if i == on else ""}">{ico(ic, 1.9, sw=2 if i != on else 2.4)}<span>{esc(lab)}</span></div>')
    home = '<div class="home"></div>' if c.sb_kind == "ios" else ""
    return f'<div class="tabbar">{"".join(items)}{home}</div>'


def browser_frame(c: Ctx, url: str, title: str, inner: str) -> str:
    r = c.r
    dots = "".join(f'<i style="background:{col}"></i>' for col in ("#ff5f57", "#febc2e", "#28c840"))
    tabs = f'<div class="btab">{esc(title)}</div>'
    if r.random() < 0.6:
        tabs += f'<div class="btab" style="background:transparent;opacity:.7;min-width:140px">{esc(r.choice(["New Tab", "Inbox", "Google", "Docs", "YouTube"]))}</div>'
    nav = f'<span style="display:flex;gap:14px;opacity:.7">{ico("back", 1.3)}{ico("chev", 1.3)}{ico("refresh", 1.2)}</span>'
    lock = ico("lock", 1.0)
    bar = (f'<div class="bbar">{nav}<div class="url"><span style="opacity:.6;margin-right:6px">{lock}</span>{esc(url)}</div>'
           f'<span style="display:flex;gap:12px;opacity:.7">{ico("star", 1.2)}{ico("vdots", 1.3)}</span></div>')
    return f'<div class="bwin"><div class="btop"><div class="dots">{dots}</div>{tabs}</div>{bar}<div class="bpage">{inner}</div></div>'


# ----------------------------------------------------------------------------
# Families (each returns inner HTML of the app area; may set ctx.* options)
# ----------------------------------------------------------------------------
FAMILIES: dict[str, dict] = {}


def family(name, desktop=False, web=0.0, tall=0.0):
    def deco(fn):
        FAMILIES[name] = {"fn": fn, "desktop_only": desktop, "web_prob": web, "tall_prob": tall}
        return fn
    return deco


def chat_line(c: Ctx) -> str:
    r = c.r
    amt = c.money(c.amount(50, 20000), dec=False)
    t = r.choice([
        "Hey, did you get the money?", "Yes just received, thanks!", "Send me the screenshot of the payment",
        f"Sent {amt} to your account", "Ok will transfer by evening", "What time are we meeting tomorrow?",
        "Running 10 mins late, start without me", "Can you share the invoice number?", "Reached home",
        "Please confirm the delivery address", "Done. Check once", "Got it, thanks a lot",
        "Call me when you are free", "Booked the tickets for Saturday", "Rent paid for this month",
        "Lol that's hilarious", "Where are you?", "Will pay you back tomorrow, promise",
        f"Transaction ID {c.digits(12)}", "Payment pending, bank server is down",
        f"Can you lend me {amt} till Friday?", "Sure, sending now", "Did you see the match last night?",
        "Don't forget to carry your ID card", "Happy birthday! Have a great one", "Mom is asking about dinner",
        f"The total comes to {amt} including tax", "Okay I'll check and let you know", "Thanks, received",
        "Please send the OTP you received", "Meeting at 4, conference room B", "See you at the station",
    ])
    return t


def pay_card(c: Ctx, out: bool, fg: str) -> str:
    r = c.r
    amt = c.money(c.amount(100, 25000), dec=r.random() < .4)
    return (f'<div style="min-width:12.5em"><div class="row g1 sm" style="opacity:.85">{ico("wallet", 1.1)}<span>{esc(r.choice(["Payment to", "Payment from", "Paid"]))} {esc(c.person().split()[0])}</span></div>'
            f'<div style="font-size:1.9em;font-weight:var(--fwb);margin:.15em 0">{esc(amt)}</div>'
            f'<div class="row g1 sm"><span class="chk" style="width:1.2em;height:1.2em;background:#25d366">{ico("check", .8, "#fff", 3)}</span><span>Payment successful</span></div></div>')


def ticks(color: str) -> str:
    return (f'<svg viewBox="0 0 18 12" width="1.15em" height="0.8em" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" '
            f'stroke-linejoin="round" style="vertical-align:-0.05em"><path d="M1 6.5l3.5 3.5L11 2M7 9.5l1 1L16 2"/></svg>')


@family("chat", tall=0.2)
def fam_chat(c: Ctx, group: bool = False) -> str:
    r = c.r
    dark = c.dark
    style = r.choice(["wa", "wa", "imsg", "tg"]) if not group else r.choice(["wa", "wa", "tg", "imsg"])
    c.variant = style + ("-group" if group else "")
    P = {
        "wa": dict(hdr="#202c33" if dark else "#008069", hdrfg="#e9edef" if dark else "#ffffff", bg="#0b141a" if dark else "#efeae2",
                   inb="#202c33" if dark else "#ffffff", outb="#005c4b" if dark else "#d9fdd3", fg="#e9edef" if dark else "#111b21",
                   outfg="#e9edef" if dark else "#111b21", sub="#8696a0" if dark else "#667781", rad=8, pat=True),
        "imsg": dict(hdr="#1c1c1e" if dark else "#f6f6f6", hdrfg="#ffffff" if dark else "#000000", bg="#000000" if dark else "#ffffff",
                     inb="#262628" if dark else "#e9e9eb", outb="#0b84fe", fg="#ffffff" if dark else "#000000", outfg="#ffffff",
                     sub="#8e8e93", rad=18, pat=False),
        "tg": dict(hdr="#212d3b" if dark else "#517da2", hdrfg="#ffffff", bg="#0e1621" if dark else "#c9dbc0",
                   inb="#182533" if dark else "#ffffff", outb="#2b5278" if dark else "#eeffde", fg="#ffffff" if dark else "#000000",
                   outfg="#ffffff" if dark else "#000000", sub="#7f91a4" if dark else "#6c7883", rad=14, pat=False),
    }[style]
    if r.random() < 0.3 and style != "imsg":
        P["outb"] = c.accent
        P["outfg"] = "#ffffff"
        P["sub"] = "rgba(255,255,255,.75)"
    c.sb_bg, c.sb_fg = P["hdr"], P["hdrfg"]
    name = c.person() if not group else r.choice(["Family ❤️", "College Gang", "Office Team", "Flat 302 Roommates", "Weekend Trek", "Project Alpha",
                                                  "Cousins Group", "Badminton Club", "Neighbours", "Study Group 2025", "Trip to Goa"])
    members = [c.person().split()[0] for _ in range(r.randint(3, 6))]
    status = r.choice(["online", f"last seen today at {c.time()}", "typing...", "tap here for contact info"]) if not group else ", ".join(members[:4]) + ", You"
    back = ico("back", 1.4, sw=2.6)
    if style == "wa":
        hdr = (f'<div class="hdr" style="background:{P["hdr"]};color:{P["hdrfg"]}">{back}{avatar(c, name, 2.4)}'
               f'<div class="grow"><div class="b ell" style="font-size:1.08em">{esc(name)}</div><div class="xs ell" style="opacity:.8">{esc(status)}</div></div>'
               f'{ico("video", 1.4)}{ico("phone", 1.3)}{ico("vdots", 1.3)}</div>')
    elif style == "imsg":
        hdr = (f'<div class="hdr" style="background:{P["hdr"]};color:{P["hdrfg"]};border-bottom:1px solid var(--line);padding:.4em 1em .6em">'
               f'<span style="color:#0b84fe" class="row">{back}<span class="pill" style="background:#0b84fe;color:#fff;padding:.05em .5em">{r.randint(1, 24)}</span></span>'
               f'<div class="grow col" style="align-items:center;gap:.2em">{avatar(c, name, 2.6)}<div class="xs row g1">{esc(name)} {ico("chev", .7, "#8e8e93")}</div></div>'
               f'<span style="color:#0b84fe">{ico("video", 1.5)}</span></div>')
    else:
        hdr = (f'<div class="hdr" style="background:{P["hdr"]};color:{P["hdrfg"]}">{back}'
               f'<div class="grow"><div class="b ell" style="font-size:1.08em">{esc(name)}</div><div class="xs ell" style="opacity:.8">{esc(status)}</div></div>'
               f'{avatar(c, name, 2.3)}</div>')
    bub_rad = P["rad"]
    sender_cols = [hsl(h, 70, 45 if not dark else 65) for h in (0, 30, 140, 200, 260, 320, 170, 80)]
    n = c.n_rows(3.1, 4)
    msgs, last_out, day_done = [], None, False
    out_ratio = r.uniform(.35, .6)
    sn_map = {m: sender_cols[i % len(sender_cols)] for i, m in enumerate(members)}
    ts_h, ts_m = r.randint(6, 22), r.randint(0, 59)
    items = []
    for i in range(n):
        if i % r.randint(6, 12) == 0:
            lab = r.choice(["TODAY", "YESTERDAY", c.fmt_date(c.date(60), "short").upper(), "Today", "Yesterday", c.fmt_date(c.date(60), "wk")])
            items.append(f'<div class="ctr" style="margin:.5em 0"><span class="xs" style="background:{"#182229" if dark else "#e1f2fb"};color:{P["sub"] if dark else "#54656f"};'
                         f'padding:.35em .8em;border-radius:.6em;box-shadow:0 1px .5px rgba(0,0,0,.1)">{esc(lab)}</span></div>' if style != "imsg"
                         else f'<div class="ctr xs" style="color:{P["sub"]};margin:.6em 0"><b>{esc(r.choice(["Today", "Yesterday"]))}</b> {c.time()}</div>')
        out = (r.random() < out_ratio) if not group else (r.random() < .3)
        ts_m += r.randint(0, 6)
        if ts_m > 59:
            ts_m -= 60
            ts_h = (ts_h + 1) % 24
        tm = c.time(hh=ts_h, mm=ts_m)
        body = chat_line(c)
        sender = r.choice(members) if (group and not out) else None
        if out and r.random() < 0.1:
            body_html = pay_card(c, out, P["outfg"])
        else:
            body_html = esc(body)
        tick_col = "#53bdeb" if r.random() < .75 else P["sub"]
        meta = f'<span class="tm" style="float:right;margin:.85em 0 -.25em .7em;font-size:.68em;color:{P["sub"] if not (out and style=="wa" and not dark) else "#667781"};white-space:nowrap">{esc(tm) if style != "imsg" else ""} {ticks(tick_col) if (out and style in ("wa", "tg")) else ""}</span>'
        if style == "imsg":
            meta = ""
        bg = P["outb"] if out else P["inb"]
        fgc = P["outfg"] if out else P["fg"]
        sn = f'<div class="b sm" style="color:{sn_map[sender]};margin-bottom:.1em">{esc(sender)}</div>' if sender else ""
        if group and not out and style == "imsg":
            av_ = avatar(c, sender, 1.9)
            wrap = f'<div class="row" style="align-items:flex-end;gap:.4em;justify-content:flex-start">{av_}'
            end = '</div>'
        else:
            wrap, end = '<div style="display:flex;justify-content:%s">' % ("flex-end" if out else "flex-start"), '</div>'
        corner = f"border-bottom-{'right' if out else 'left'}-radius:{max(bub_rad * .25, 3):.0f}px" if r.random() < .3 else ""
        items.append(f'{wrap}<div style="max-width:78%;background:{bg};color:{fgc};padding:.45em .7em .4em;border-radius:{bub_rad}px;{corner};'
                     f'box-shadow:0 1px .5px rgba(0,0,0,.13);line-height:1.3">{sn}{body_html}{meta}<div style="clear:both"></div></div>{end}')
    pat = "background-image:radial-gradient(rgba(128,128,128,.10) 1.3px,transparent 1.4px);background-size:24px 24px;" if P["pat"] else ""
    if style == "imsg":
        inp = (f'<div class="row g2" style="padding:.5em .8em .8em;background:{P["bg"]}"><span class="chk" style="width:2em;height:2em;background:{"#2c2c2e" if dark else "#e9e9eb"};color:#8e8e93">{ico("plus", 1.1)}</span>'
               f'<div class="grow row" style="border:1px solid {"#3a3a3c" if dark else "#c8c8cc"};border-radius:99px;padding:.4em .9em;color:#8e8e93">{esc(r.choice(["iMessage", "Text Message"]))}<span style="margin-left:auto">{ico("mic", 1.1)}</span></div></div>')
    else:
        inp = (f'<div class="row g1" style="padding:.45em .5em;background:transparent"><div class="grow row g1" style="background:{P["inb"]};color:{P["sub"]};border-radius:99px;padding:.55em .9em">'
               f'{ico("camera", 1.2)}<span class="grow">{"Message" if style == "wa" else "Message"}</span>{ico("clip", 1.2)}{ico("camera", 1.2)}</div>'
               f'<span class="chk" style="width:2.6em;height:2.6em;background:{c.accent if style != "wa" else "#00a884"};color:#fff">{ico("mic", 1.3, "#fff")}</span></div>')
    c.tab = None
    home = '<div class="home" style="position:static;margin:.3em auto .5em"></div>' if c.sb_kind == "ios" else ""
    return (f'{hdr}<div style="flex:1;min-height:0;overflow:hidden;display:flex;flex-direction:column;justify-content:flex-end;gap:.28em;padding:.6em .6em;background-color:{P["bg"]};{pat}">'
            f'{"".join(items)}</div><div style="background:{P["bg"]}">{inp}</div>{home if c.mobile else ""}')


@family("group_chat", tall=0.2)
def fam_group(c: Ctx) -> str:
    return fam_chat(c, group=True)


SMS_BANK = [
    "{otp} is your OTP for transaction of {amt} at {merch}. Valid for 10 mins. Do not share it with anyone. -{bank}",
    "Dear Customer, {amt} debited from A/c XX{ac4} on {date} to VPA {upi}. UPI Ref No {ref}. If not you, call 1800-{n4}-{n4b}. -{bank}",
    "Rs {num} credited to your A/c XX{ac4} on {date} via UPI Ref {ref}. Avl Bal: {bal}. -{bank}",
    "{otp} is your verification code for {app}. Do not share this code with anyone.",
    "Your {merch} order #{ord} has been dispatched and will arrive by {date}. Track at bit.ly/{short}",
    "Hi {first}, your cab is arriving. Share OTP {otp4} with your driver. Vehicle KA{n2}MX{n4}.",
    "{otp} is the OTP to log in to your {bank} NetBanking. It is valid for 5 minutes. Never share your OTP.",
    "Your {carrier} prepaid recharge of {amt} is successful. Validity till {date}. Txn ID {ref}.",
]
SMS_US = [
    "{bank}: Card ending {ac4} was used for {amt} at {merch} on {date}. Reply STOP to opt out.",
    "{otp} is your {app} verification code. It expires in 10 minutes. Don't share it with anyone.",
    "{bank} Alert: Your balance is {bal}. A deposit of {amt} was posted on {date}.",
    "Your {merch} order #{ord} has shipped! Track it here: bit.ly/{short}",
    "Use code {otp} to sign in to {app}. If you didn't request this, ignore this message.",
    "Your driver {first} is arriving in 3 min. PIN: {otp4}. Plate: {n4}-{n2}K",
    "{bank}: Zelle payment of {amt} from {person} was received on {date}. Ref {ref}.",
    "Reminder: Your appointment at {merch} is on {date} at {time}. Reply C to confirm.",
]


@family("sms_otp", tall=0.2)
def fam_sms(c: Ctx) -> str:
    r = c.r
    dark = c.dark
    ios = r.random() < 0.55
    c.variant = "ios" if ios else "gmsg"
    sender = r.choice(["VM-HDFCBK", "AX-ICICIB", "JD-SBIUPI", "BP-AMAZON", "VK-PAYTMB", "AD-AIRTEL", "TX-SWIGGY", "CP-AXISBK", "VM-UBERIN"]) if c.region == "in" \
        else r.choice(["Chase", "22395", "89203", "+1 (415) 555-0172", "Venmo", "AMZN", "Uber", "Bank of America", "Google", "+44 7700 900123"])
    pool = SMS_BANK if c.region == "in" else SMS_US
    n = c.n_rows(5.2, 3)
    items = []
    d0 = c.date(10)
    for i in range(n):
        def fmt(t):
            return t.format(otp=c.digits(6), otp4=c.digits(4), amt=c.money(c.amount(100, 30000)), merch=c.merchant(), bank=c.bank().upper() if c.region == "in" else c.bank(),
                            ac4=c.digits(4), date=c.fmt_date(c.date(5)), upi=c.upi_id(), ref=c.digits(12), n4=c.digits(4), n4b=c.digits(4), n2=c.digits(2),
                            num=group_digits(int(c.amount(100, 30000)), True), bal=c.money(c.amount(1000, 200000)), app=r.choice(["Google", "Instagram", "Amazon", "Uber", "Swiggy", "PhonePe", "Flipkart", "Zomato"]),
                            ord=c.digits(9), short=c.alnum(6).lower(), first=r.choice(FIRST), carrier=r.choice(["Jio", "Airtel", "Vi"]), person=c.person(), time=c.time())
        txt = fmt(r.choice(pool))
        if i % 3 == 0 or r.random() < .2:
            if ios:
                items.append(f'<div class="ctr xs" style="color:#8e8e93;margin:.8em 0 .1em"><b>{esc(r.choice(["Today", "Yesterday", "Mon", "Fri"]))}</b> {c.time()}</div>')
            else:
                items.append(f'<div class="ctr xs mu" style="margin:.8em 0 .1em">{esc(c.fmt_date(d0, "wk"))} • {c.time()}</div>')
        if r.random() < .12:
            out = True
            txt = r.choice(["Ok thanks", "Got the OTP", "Received", "STOP", "Yes", "Done"])
        else:
            out = False
        if ios:
            bg = "#0b84fe" if out else ("#262628" if dark else "#e9e9eb")
            col = "#fff" if (out or dark) else "#000"
            rad = "1.15em"
        else:
            bg = c.accent if out else ("#2b2b30" if dark else "#e8eaf6" if r.random() < .5 else "#f1f3f4")
            col = "#fff" if out else ("#e8eaed" if dark else "#202124")
            rad = "1.3em"
        items.append(f'<div style="display:flex;justify-content:{"flex-end" if out else "flex-start"}"><div style="max-width:80%;background:{bg};color:{col};padding:.55em .8em;border-radius:{rad};line-height:1.3;overflow-wrap:anywhere">{esc(txt)}</div></div>')
    if ios:
        c.sb_bg = "#1c1c1e" if dark else "#f6f6f6"
        hdr = (f'<div class="hdr" style="background:{c.sb_bg};border-bottom:1px solid var(--line);padding:.3em 1em .6em"><span style="color:#0b84fe" class="row">{ico("back", 1.4, sw=2.6)}</span>'
               f'<div class="grow col" style="align-items:center;gap:.2em"><div class="av" style="width:2.6em;height:2.6em;border-radius:50%;background:linear-gradient(#9ca3af,#6b7280)">{ico("user", 1.4, "#fff")}</div>'
               f'<div class="xs row g1">{esc(sender)} {ico("chev", .7, "#8e8e93")}</div></div><span style="width:1.4em"></span></div>')
        inp = f'<div class="row g2" style="padding:.5em .8em .3em"><span class="chk" style="width:2em;height:2em;background:{"#2c2c2e" if dark else "#e9e9eb"};color:#8e8e93">{ico("plus", 1.1)}</span><div class="grow row" style="border:1px solid {"#3a3a3c" if dark else "#c8c8cc"};border-radius:99px;padding:.4em .9em;color:#8e8e93">Text Message • SMS</div></div>'
    else:
        hdr = (f'<div class="hdr" style="background:var(--bg)">{ico("back", 1.4)}<div class="grow"><div class="b ell">{esc(sender)}</div></div>{ico("phone", 1.3)}{ico("vdots", 1.3)}</div>')
        inp = f'<div class="row g1" style="padding:.5em"><div class="grow row g1" style="background:var(--bg2);border-radius:99px;padding:.6em 1em;color:var(--fg2)">Text message</div><span class="chk" style="width:2.6em;height:2.6em;background:{c.accent};color:#fff">{ico("send", 1.2, "#fff")}</span></div>'
    c.tab = None
    return (f'{hdr}<div style="flex:1;min-height:0;overflow:hidden;display:flex;flex-direction:column;justify-content:flex-end;gap:.4em;padding:.6em .8em">'
            f'{"".join(items)}</div>{inp}')


def detail_rows(rows: list[tuple[str, str]], cls: str = "") -> str:
    out = []
    for k, v in rows:
        out.append(f'<div class="row g2" style="align-items:flex-start;padding:.55em 0"><span class="mu sm" style="width:40%;flex:none">{esc(k)}</span>'
                   f'<span class="grow r wrap" style="font-weight:var(--fw)">{esc(v) if not v.startswith("<") else v}</span></div>')
    return "".join(out)


@family("upi_receipt", web=0.12)
def fam_upi(c: Ctx) -> str:
    r = c.r
    var = r.choice(["gpay", "phonepe", "slip"])
    c.variant = var
    amt = c.amount(20, 50000)
    payee = c.person() if r.random() < .6 else c.merchant()
    upi = c.upi_id(payee if " " in payee else None)
    d = c.date(200)
    dt = f"{c.fmt_date(d, r.choice(['dmy_mon', 'mon_dmy']))}, {c.time()}"
    utr = c.digits(12)
    bank = c.bank()
    ac4 = c.digits(4)
    tid = r.choice([c.alnum(r.choice([16, 20]), "T"), c.alnum(10, "CICA").lower().upper(), "AXI" + c.digits(13)])
    rows = [("Date & time", dt), ("UPI transaction ID", utr), ("Transaction ID", tid), ("From", f"{bank} ({ac4})"), ("To", upi), ("Reference No.", c.digits(10))]
    r.shuffle(rows)
    rows = rows[:r.randint(4, 6)]
    note = r.choice(["", "", "Rent", "Dinner split", "Thanks", "Groceries", "Gift", "Lunch"])
    if note:
        rows.append(("Note", note))
    chkc = c.good
    big = f"font-size:{r.uniform(2.4, 3.2):.2f}em;font-weight:var(--fwb)"
    if var == "gpay":
        c.sb_bg, c.sb_fg = "var(--bg)", "var(--fg)"
        c.tab = None
        top = (f'<div class="col" style="align-items:center;padding:2.2em 1.2em 1em;gap:.5em"><span class="chk" style="width:4.2em;height:4.2em;background:{chkc}">{ico("check", 2.4, "#fff", 3.2)}</span>'
               f'<div style="{big};margin-top:.3em">{esc(c.money(amt))}</div><div class="mu">Paid to</div><div class="b lg ctr">{esc(payee)}</div><div class="mu sm">{esc(upi)}</div>'
               f'<div class="pill" style="background:{"rgba(48,209,88,.15)" if c.dark else "#e6f4ea"};color:{chkc};margin-top:.4em">Completed</div></div>')
        card = f'<div class="card" style="margin:.5em 1em">{detail_rows(rows)}</div>'
        btns = f'<div class="row g2" style="padding:1em"><div class="btn o grow">{ico("share", 1.1)}Share receipt</div><div class="btn grow">Done</div></div>'
        foot = f'<div class="ctr mu xs" style="padding:1em">Powered by UPI &nbsp;|&nbsp; {esc(bank)}</div>'
        return f'<div class="hdr" style="background:var(--bg)">{ico("close", 1.4)}<span class="grow"></span>{ico("vdots", 1.3)}</div>{top}{card}<div style="margin-top:auto">{foot}{btns}</div>'
    if var == "phonepe":
        grad = hero_gradient(c)
        c.sb_bg, c.sb_fg = "transparent", "#fff"
        c.sb_overlay = True
        c.tab = None
        top = (f'<div style="background:{grad};color:#fff;padding:calc(var(--sbh) + .8em) 1.2em 2.2em;">'
               f'<div class="row" style="margin-bottom:1em">{ico("back", 1.4, "#fff")}<span class="grow"></span>{ico("share", 1.3, "#fff")}</div>'
               f'<div class="row g2"><span class="chk" style="width:3em;height:3em;background:#fff">{ico("check", 1.8, chkc, 3.4)}</span><div><div class="b lg">Payment Successful</div><div class="sm" style="opacity:.85">{esc(dt)}</div></div></div>'
               f'<div style="{big};margin-top:.7em">{esc(c.money(amt))}</div><div class="sm" style="opacity:.9;margin-top:.15em">Paid to <b>{esc(payee)}</b></div></div>')
        card = f'<div class="card" style="margin:-1.2em 1em .6em;position:relative">{detail_rows(rows)}</div>'
        extra = (f'<div class="card row g2" style="margin:.4em 1em">{ico("swap", 1.3, "var(--accent-t)")}<span class="grow b">Split this expense</span>{ico("chev", 1.1)}</div>'
                 f'<div class="card row g2" style="margin:.4em 1em">{ico("file", 1.3, "var(--accent-t)")}<span class="grow b">View Transaction History</span>{ico("chev", 1.1)}</div>')
        foot = f'<div class="ctr mu xs" style="padding:1em">Powered by UPI &nbsp;|&nbsp; {esc(r.choice(BANKS_IN if c.region == "in" else BANKS_US))}</div>'
        return f'{top}{card}{extra}<div style="margin-top:auto">{foot}</div>'
    # slip
    c.tab = None
    head = (f'<div class="hdr" style="background:var(--accent);color:#fff">{ico("back", 1.4, "#fff")}<span class="grow b">{esc(r.choice(["Transaction Details", "Payment Receipt", "Money Sent"]))}</span>{ico("share", 1.3, "#fff")}</div>')
    c.sb_bg, c.sb_fg = "var(--accent)", "#fff"
    body = (f'<div class="card" style="margin:1em;text-align:center;padding:1.4em 1em"><span class="chk" style="width:3.4em;height:3.4em;background:{chkc};margin:0 auto">{ico("check", 2, "#fff", 3.2)}</span>'
            f'<div class="b" style="margin-top:.5em;color:{chkc}">{esc(r.choice(["Money Sent Successfully", "Payment Successful", "Transfer Completed"]))}</div>'
            f'<div style="{big};margin:.3em 0">{esc(c.money(amt))}</div><div class="mu sm">to {esc(payee)}</div><div class="hr" style="margin:1em 0 .4em"></div>'
            f'<div style="text-align:left">{detail_rows(rows)}</div></div>')
    btns = f'<div class="row g2" style="padding:1em"><div class="btn grow">Back to Home</div></div>'
    return head + body + f'<div class="card row g2" style="margin:0 1em">{ico("file", 1.2)}<span class="grow">Download receipt (PDF)</span>{ico("download", 1.2)}</div><div style="margin-top:auto">{btns}</div>'


def txn_row(c: Ctx, name: str, sub: str, amt: float, credit: bool, show_av=True) -> str:
    col = c.good if credit else "var(--fg)"
    return (f'<div class="li">{avatar(c, name, 2.6, c.av_shape) if show_av else ""}<div class="grow"><div class="ell b" style="font-weight:var(--fw)">{esc(name)}</div>'
            f'<div class="xs mu ell">{esc(sub)}</div></div><div class="r nw b" style="color:{col}">{esc(c.money(amt, sign=credit))}</div></div>')


@family("bank_balance", web=0.1, tall=0.2)
def fam_bank_balance(c: Ctx) -> str:
    r = c.r
    var = r.choice(["card", "plain"])
    c.variant = var
    bank = c.bank()
    name = c.person()
    bal = c.amount(500, 900000)
    ac = f"•••• {c.digits(4)}"
    c.av_shape = r.choice(["circle", "squircle"])
    grad = hero_gradient(c)
    quick = [("send", "Send"), ("qr", "Scan"), ("card", "Cards"), ("file", "Bills"), ("plus", "More")][: r.randint(4, 5)]
    qhtml = "".join(f'<div class="col" style="align-items:center;gap:.35em;flex:1"><span class="chk" style="width:3em;height:3em;background:var(--bg2);color:var(--accent-t)">{ico(i, 1.4)}</span><span class="xs">{esc(l)}</span></div>' for i, l in quick)
    n = c.n_rows(3.9, 3)
    rows = []
    for _ in range(n):
        credit = r.random() < .25
        nm = c.person() if (credit or r.random() < .2) else c.merchant()
        rows.append(txn_row(c, nm, f"{c.fmt_date(c.date(40), 'short')} • {r.choice(['UPI', 'Card', 'NEFT', 'IMPS', 'Debit', 'Auto-pay'])}", c.amount(30, 40000), credit))
    c.tab = ([("home", "Home"), ("send", "Pay"), ("card", "Cards"), ("chart", "Insights"), ("user", "Profile")], 0)
    greet = r.choice(["Good morning", "Good afternoon", "Welcome back", "Hello"])
    if var == "card":
        c.sb_bg, c.sb_fg = "var(--bg)", "var(--fg)"
        top = (f'<div class="row" style="padding:.8em 1em">{avatar(c, name, 2.4)}<div class="grow" style="margin-left:.7em"><div class="xs mu">{esc(greet)}</div><div class="b">{esc(name)}</div></div>{ico("bell", 1.4)}</div>'
               f'<div style="margin:.4em 1em;border-radius:calc(var(--r) + 6px);background:{grad};color:#fff;padding:1.2em 1.1em;box-shadow:var(--sh)">'
               f'<div class="row"><span class="sm" style="opacity:.85">Available balance</span><span class="grow"></span><span class="sm" style="opacity:.85">{esc(bank)}</span></div>'
               f'<div style="font-size:{r.uniform(2.1, 2.8):.2f}em;font-weight:var(--fwb);margin:.25em 0 .6em">{esc(c.money(bal))}</div>'
               f'<div class="row sm" style="opacity:.9"><span>Savings A/c {ac}</span><span class="grow"></span><span>Tap to hide</span></div></div>')
    else:
        top = (f'<div class="row" style="padding:.8em 1em">{ico("menu", 1.4)}<div class="grow ctr b">{esc(bank)}</div>{ico("bell", 1.4)}</div>'
               f'<div class="ctr" style="padding:1em"><div class="mu sm">Total balance</div><div style="font-size:{r.uniform(2.4, 3.2):.2f}em;font-weight:var(--fwb)">{esc(c.money(bal))}</div>'
               f'<div class="pill" style="background:var(--bg2);color:var(--fg2)">Savings {ac}</div></div>')
    return (f'{top}<div class="row" style="padding:1em .5em .6em">{qhtml}</div><div class="row" style="padding:.4em 1em"><b class="grow">Recent transactions</b><span style="color:var(--accent-t)" class="sm">See all</span></div>'
            f'<div style="background:var(--card);border-radius:var(--r) var(--r) 0 0;flex:1;min-height:0;overflow:hidden">{"".join(rows)}</div>')


@family("bank_statement", web=0.45, tall=0.15)
def fam_statement(c: Ctx) -> str:
    r = c.r
    bank = c.bank()
    name = c.person()
    var = r.choice(["table", "table", "banded"])
    c.variant = var
    n = c.n_rows(2.4 if not c.mobile else 2.9, 2)
    bal = c.amount(5000, 400000)
    open_bal = bal
    d = c.date(300)
    rows = []
    desc_pool = lambda: r.choice([f"UPI/{c.digits(12)}/{c.merchant()}", f"NEFT-{c.alnum(10)}-{c.person()}", f"ATM WDL {c.alnum(6)} {r.choice(PLACES)}",
                                  f"POS {c.digits(6)} {c.merchant()}", f"IMPS/{c.digits(10)}/{c.person().split()[0]}", f"SALARY {r.choice(COMPANIES)}",
                                  f"ACH D- {r.choice(['LIC', 'SIP', 'HOME LOAN EMI', 'Netflix'])}-{c.digits(6)}", f"INT.PD {c.fmt_date(d, 'short')}", f"CHQ {c.digits(6)}"])
    for _ in range(n):
        d += _dt.timedelta(days=r.randint(0, 3))
        credit = r.random() < .3
        amt = c.amount(50, 60000 if credit else 20000)
        bal += amt if credit else -amt
        if bal < 0:
            bal += 2 * amt
            credit = True
        rows.append((d, desc_pool(), None if credit else amt, amt if credit else None, bal))
    dfmt = r.choice(["num", "dash", "short", "yy", "yy"]) if not c.mobile else r.choice(["short", "yy", "yy"])
    nos = r.random() < 0.7  # most statements omit the currency symbol in the amount columns
    mm = lambda v: esc(c.money(v, abs_=True, nosym=nos))
    trs = "".join(f'<tr style="{"background:var(--bg2)" if (var == "banded" and i % 2) else ""}"><td class="nw">{esc(c.fmt_date(dd, dfmt))}</td><td style="overflow-wrap:anywhere;line-height:1.2">{esc(ds)}</td>'
                  f'<td class="n bad">{mm(db) if db else ""}</td><td class="n good">{mm(cr) if cr else ""}</td><td class="n">{mm(bl)}</td></tr>'
                  for i, (dd, ds, db, cr, bl) in enumerate(rows))
    c.tab = None
    hdr = (f'<div class="hdr">{ico("back", 1.4)}<div class="grow b">Account Statement</div>{ico("download", 1.3)}</div>' if c.mobile else "")
    info = (f'<div class="card" style="margin:.7em .8em;padding:.8em 1em"><div class="row"><b class="grow">{esc(bank)}</b><span class="mu sm">Statement</span></div>'
            f'<div class="sm mu" style="margin-top:.3em">{esc(name)} \u2022 A/c No. XXXX{c.digits(4)} \u2022 IFSC {c.alnum(4)}0{c.digits(6)}</div>'
            f'<div class="row sm" style="margin-top:.5em;gap:1.2em"><span>Period: {esc(c.fmt_date(rows[0][0], "dmy_mon"))} - {esc(c.fmt_date(rows[-1][0], "dmy_mon"))}</span></div>'
            f'<div class="row sm" style="margin-top:.5em"><span class="grow">Opening: <b>{esc(c.money(open_bal))}</b></span><span>Closing: <b>{esc(c.money(rows[-1][4]))}</b></span></div></div>')
    cw = ("18%", "24%", "19%", "19%", "20%") if c.mobile else ("17%", "32%", "16%", "16%", "19%")
    cols = "".join(f'<col style="width:{x}">' for x in cw)
    table = (f'<div style="padding:0 .8em;flex:1;min-height:0;overflow:hidden;font-size:{.68 if c.mobile else .95}em"><table class="tbl" style="table-layout:fixed"><colgroup>{cols}</colgroup><thead><tr><th>Date</th><th>Description</th><th class="n">Debit</th><th class="n">Credit</th><th class="n">Balance</th></tr></thead>'
             f'<tbody>{trs}</tbody></table></div>')
    return hdr + info + table


@family("ecom_order", web=0.3, tall=0.15)
def fam_ecom(c: Ctx) -> str:
    r = c.r
    var = r.choice(["summary", "confirm"])
    c.variant = var
    shop = r.choice(["ShopKart", "Amazon", "Flipkart", "Myntra", "Nykaa", "eBay", "Etsy", "Walmart", "Target", "IKEA", "Zalando", "Meesho"])
    items = r.sample(PRODUCTS, r.randint(2, 5))
    sub = 0.0
    lines = []
    for nm, em, price in items:
        k = 1.0 if c.cur["code"] == "INR" else 0.045
        pr = round(price * k * r.uniform(.8, 1.3), 2) if k != 1 else float(price)
        q = r.choice([1, 1, 1, 2, 3])
        sub += pr * q
        h = (sum(map(ord, nm)) * 7) % 360
        lines.append(f'<div class="li" style="align-items:flex-start"><div style="width:3.8em;height:3.8em;border-radius:.6em;background:linear-gradient(135deg,hsl({h} 70% 88%),hsl({(h + 40) % 360} 70% 78%));display:flex;align-items:center;justify-content:center;font-size:1.7em;flex:none">{em}</div>'
                     f'<div class="grow"><div class="b" style="font-weight:var(--fw);line-height:1.25">{esc(nm)}</div><div class="xs mu" style="margin-top:.25em">Qty: {q} • {esc(r.choice(["Seller: " + r.choice(COMPANIES), "Size: M", "Colour: Black", "Free returns"]))}</div></div>'
                     f'<div class="r nw b">{esc(c.money(pr * q))}</div></div>')
    ship = 0.0 if r.random() < .5 else round(sub * r.uniform(.02, .06), 2)
    disc = round(sub * r.uniform(.05, .2), 2) if r.random() < .6 else 0.0
    taxr = r.choice([5, 8, 12, 18, 7.5, 10, 20])
    tax = round((sub - disc) * taxr / 100, 2)
    total = round(sub - disc + ship + tax, 2)
    taxn = "GST" if c.region == "in" else r.choice(["Tax", "VAT", "Sales Tax"])
    sums = [("Subtotal", c.money(sub)), ("Shipping", c.money(ship) if ship else "FREE")]
    if disc:
        sums.append(("Discount", "-" + c.money(disc)))
    sums.append((f"{taxn} ({taxr}%)", c.money(tax)))
    srows = "".join(f'<div class="row" style="padding:.28em 0"><span class="grow mu">{esc(k)}</span><span class="{"good" if k == "Discount" else ""}">{esc(v)}</span></div>' for k, v in sums)
    oid = r.choice([f"{c.digits(3)}-{c.digits(7)}-{c.digits(7)}", f"OD{c.digits(18)}", f"#{c.digits(9)}", f"{c.alnum(10)}"])
    d = c.date(150)
    pay = r.choice(["UPI", "Visa •••• " + c.digits(4), "Mastercard •••• " + c.digits(4), "Cash on Delivery", "Net Banking", "Apple Pay", "PayPal"])
    addr = f"{c.person()}, {r.randint(1, 999)} {r.choice(['MG Road', 'Park Avenue', 'Elm Street', 'Lake View Road', 'Sector 14'])}, {r.choice(CITIES)} {c.digits(6) if c.region == 'in' else c.digits(5)}"
    c.tab = None if not c.mobile else None
    head = (f'<div class="hdr">{ico("back", 1.4)}<div class="grow b">{"Order Summary" if var == "summary" else "Order Confirmed"}</div>{ico("cart", 1.3)}</div>')
    ban = ""
    if var == "confirm":
        ban = (f'<div class="row g2" style="padding:1em;background:{"rgba(48,209,88,.12)" if c.dark else "#e8f5e9"}"><span class="chk" style="width:2.6em;height:2.6em;background:{c.good}">{ico("check", 1.5, "#fff", 3)}</span>'
               f'<div><div class="b">Thank you, your order is placed!</div><div class="sm mu">Arriving {esc(c.fmt_date(d + _dt.timedelta(days=4), "wk"))}</div></div></div>')
    meta = (f'<div class="card" style="margin:.7em .8em"><div class="row"><span class="mu sm grow">Order ID</span><b class="sm">{esc(oid)}</b></div>'
            f'<div class="row" style="margin-top:.3em"><span class="mu sm grow">Placed on</span><span class="sm">{esc(c.fmt_date(d))}</span></div>'
            f'<div class="row" style="margin-top:.3em"><span class="mu sm grow">Sold by</span><span class="sm">{esc(shop)}</span></div></div>')
    itemsc = f'<div class="card" style="margin:.7em .8em;padding:.2em 0">{"".join(lines)}</div>'
    tot = (f'<div class="card" style="margin:.7em .8em"><div class="b" style="margin-bottom:.3em">Price details</div>{srows}<div class="hr" style="margin:.5em 0"></div>'
           f'<div class="row b lg"><span class="grow">Order Total</span><span>{esc(c.money(total))}</span></div></div>')
    addrc = (f'<div class="card" style="margin:.7em .8em"><div class="b" style="margin-bottom:.3em">Delivery address</div><div class="sm mu">{esc(addr)}</div>'
             f'<div class="b" style="margin:.8em 0 .3em">Payment method</div><div class="sm mu">{esc(pay)}</div></div>')
    btn = f'<div style="padding:.8em;margin-top:auto"><div class="btn">{esc(r.choice(["Track Order", "Continue Shopping", "Download Invoice", "View Order Details"]))}</div></div>'
    return head + ban + f'<div style="flex:1;min-height:0;overflow:hidden;background:var(--bg2)">{meta}{itemsc}{tot}{addrc}</div>' + btn


def compact(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n / 1000:.1f}K" if n < 100_000 else f"{n // 1000}K"
    return f"{n:,}"


@family("social_post", web=0.25, tall=0.2)
def fam_social(c: Ctx) -> str:
    r = c.r
    var = r.choice(["feed", "detail", "insta"])
    c.variant = var
    verified = lambda: f'<span class="chk" style="width:1.05em;height:1.05em;background:#1d9bf0;vertical-align:middle;margin-left:.2em;display:inline-flex">{ico("check", .75, "#fff", 3.4)}</span>'
    c.tab = ([("home", "Home"), ("search", "Search"), ("bell", "Alerts"), ("mail", "Messages")], 0) if c.mobile else None

    def counts(big=False):
        vals = [(r.randint(2, 4000), "reply"), (r.randint(5, 20000), "repost"), (r.randint(10, 600000), "heart"), (r.randint(1000, 4000000), "chart")]
        return "".join(f'<span class="row g1 mu" style="flex:1">{ico(i, 1.15)}<span class="sm">{compact(v)}</span></span>' for v, i in vals) + f'<span class="mu">{ico("share", 1.1)}</span>'

    def post(i=0, long=False):
        nm = c.person()
        hdl = "@" + nm.lower().replace(" ", r.choice(["_", "", "."])) + (c.digits(2) if r.random() < .4 else "")
        body = r.choice(SOCIAL_BODIES)
        if long:
            body += " " + r.choice(SOCIAL_BODIES)
        tags = " ".join(r.sample(["#coding", "#india", "#travel", "#monday", "#startup", "#fitness", "#AI", "#cricket", "#foodie"], r.randint(0, 2)))
        age = r.choice([f"{r.randint(1, 59)}m", f"{r.randint(1, 23)}h", c.fmt_date(c.date(60), "short")])
        img = ""
        if r.random() < .35:
            h = r.randint(0, 360)
            img = f'<div style="height:{r.randint(8, 13)}em;border-radius:.9em;margin-top:.6em;background:linear-gradient(135deg,hsl({h} 70% 60%),hsl({h + 60} 70% 45%))"></div>'
        return (f'<div style="padding:.8em 1em;border-bottom:1px solid var(--line)"><div class="row" style="align-items:flex-start;gap:.7em">{avatar(c, nm, 2.7)}'
                f'<div class="grow"><div class="row g1" style="flex-wrap:nowrap"><b class="ell">{esc(nm)}</b>{verified() if r.random() < .4 else ""}<span class="mu sm ell">{esc(hdl)} · {esc(age)}</span></div>'
                f'<div style="margin-top:.2em;line-height:1.35">{esc(body)} <span style="color:var(--accent-t)">{esc(tags)}</span></div>{img}'
                f'<div class="row" style="margin-top:.7em;padding-right:.5em">{counts()}</div></div></div></div>')

    if var == "feed":
        n = c.n_rows(9.5, 1)
        head = (f'<div class="hdr" style="background:var(--bar);border-bottom:1px solid var(--line)">{avatar(c, c.person(), 2)}<span class="grow ctr b" style="font-size:1.2em">{esc(r.choice(["Home", "For you", "Feed"]))}</span>{ico("gear", 1.3)}</div>')
        return head + f'<div style="flex:1;min-height:0;overflow:hidden">{"".join(post(i, r.random() < .3) for i in range(n))}</div>'
    if var == "detail":
        nm = c.person()
        hdl = "@" + nm.lower().replace(" ", "_")
        d = c.date(200)
        body = r.choice(SOCIAL_BODIES) + " " + r.choice(SOCIAL_BODIES)
        head = f'<div class="hdr" style="border-bottom:1px solid var(--line)">{ico("back", 1.4)}<b class="grow" style="font-size:1.15em">Post</b></div>'
        main = (f'<div style="padding:1em"><div class="row g2">{avatar(c, nm, 3)}<div class="grow"><div class="b">{esc(nm)}{verified()}</div><div class="mu sm">{esc(hdl)}</div></div>{ico("vdots", 1.3)}</div>'
                f'<div style="font-size:{r.uniform(1.15, 1.4):.2f}em;line-height:1.35;margin:.8em 0">{esc(body)}</div>'
                f'<div class="mu sm">{esc(c.time())} · {esc(c.fmt_date(d, "mon_dmy"))} · <b style="color:var(--fg)">{compact(r.randint(2000, 3000000))}</b> Views</div></div>'
                f'<div class="row g3 sm" style="padding:.8em 1em;border-top:1px solid var(--line);border-bottom:1px solid var(--line)"><span><b>{compact(r.randint(5, 4000))}</b> <span class="mu">Reposts</span></span><span><b>{compact(r.randint(2, 900))}</b> <span class="mu">Quotes</span></span><span><b>{compact(r.randint(50, 200000))}</b> <span class="mu">Likes</span></span></div>'
                f'<div class="row" style="padding:.8em 1.5em;justify-content:space-between;border-bottom:1px solid var(--line)">{ico("reply", 1.3)}{ico("repost", 1.3)}{ico("heart", 1.3)}{ico("bookmark", 1.3)}{ico("share", 1.3)}</div>')
        n = c.n_rows(9, 0)
        return head + f'<div style="flex:1;min-height:0;overflow:hidden">{main}{"".join(post() for _ in range(n))}</div>'
    # insta
    nm = c.person().lower().replace(" ", r.choice(["_", "."]))
    h = r.randint(0, 360)
    likes = r.randint(120, 90000)
    cap = r.choice(SOCIAL_BODIES)
    head = f'<div class="hdr" style="justify-content:space-between"><b style="font-size:1.35em;font-style:italic">{esc(r.choice(["Instagram", "Gram", "Snapgram"]))}</b>{ico("heart", 1.4)}{ico("send", 1.4)}</div>'
    h2 = f'<div class="row g2" style="padding:.7em 1em">{avatar(c, nm, 2.4)}<div class="grow"><b>{esc(nm)}</b><div class="xs mu">{esc(r.choice(CITIES))}</div></div>{ico("vdots", 1.3)}</div>'
    sq = min(c.W, 520 if not c.mobile else c.W)
    pic = (f'<div style="height:{min(c.W, 470) if c.mobile else 22}{"px" if c.mobile else "em"};background:linear-gradient({r.randint(0, 360)}deg,hsl({h} 75% 62%),hsl({h + 70} 80% 48%),hsl({h + 140} 70% 55%))"></div>')
    acts = f'<div class="row g2" style="padding:.7em 1em">{ico("heart", 1.5)}{ico("reply", 1.5)}{ico("send", 1.5)}<span class="grow"></span>{ico("bookmark", 1.5)}</div>'
    cp = (f'<div style="padding:0 1em"><div class="b">{likes:,} likes</div><div style="margin-top:.2em"><b>{esc(nm)}</b> {esc(cap)}</div>'
          f'<div class="mu sm" style="margin-top:.3em">View all {r.randint(3, 900)} comments</div><div class="xs mu" style="margin-top:.3em;text-transform:uppercase">{r.randint(1, 23)} hours ago</div></div>')
    return head + f'<div style="flex:1;min-height:0;overflow:hidden">{h2}{pic}{acts}{cp}</div>'


@family("email_inbox", web=0.3, tall=0.2)
def fam_inbox(c: Ctx) -> str:
    r = c.r
    c.variant = "inbox"
    c.tab = ([("mail", "Mail"), ("video", "Meet")], 0) if c.mobile and r.random() < .5 else None
    n = c.n_rows(4.6, 3)
    rows = []
    senders = [c.person() for _ in range(8)] + COMPANIES[:6] + ["Google", "LinkedIn", "Amazon", "GitHub", "Netflix", "HDFC Bank", "Swiggy", "Notion"]
    for i in range(n):
        sd = r.choice(senders)
        subj, prev = r.choice(EMAIL_SUBJECTS)
        subj = subj.format(n=c.digits(6), co=r.choice(COMPANIES))
        unread = r.random() < .45
        age = r.choice([c.time(), c.time(), c.fmt_date(c.date(30), "short"), c.fmt_date(c.date(30), "short")])
        star = f'<span style="color:#f4b400">{ico("star", 1.1, "currentColor", 2, "currentColor")}</span>' if r.random() < .12 else f'<span class="mu" style="opacity:.5">{ico("star", 1.1)}</span>'
        rows.append(f'<div class="li" style="align-items:flex-start;gap:.8em;padding:.7em 1em">{avatar(c, sd, 2.7)}<div class="grow"><div class="row"><span class="grow ell" style="font-weight:{"var(--fwb)" if unread else "var(--fw)"}">{esc(sd)}</span>'
                    f'<span class="xs nw" style="color:{"var(--fg)" if unread else "var(--fg2)"};font-weight:{"var(--fwb)" if unread else "var(--fw)"}">{esc(age)}</span></div>'
                    f'<div class="ell" style="font-weight:{"var(--fwb)" if unread else "var(--fw)"};font-size:.95em">{esc(subj)}</div><div class="row g2"><span class="mu sm grow ell">{esc(prev)} your account...</span>{star}</div></div></div>')
    search = (f'<div class="hdr" style="background:var(--bg)"><div class="grow row g2" style="background:var(--bg2);border-radius:99px;padding:.65em 1em">{ico("menu", 1.3)}<span class="grow mu">{esc(r.choice(["Search in mail", "Search mail", "Search"]))}</span>{avatar(c, c.person(), 1.9)}</div></div>')
    lab = f'<div class="sect" style="padding-top:.4em;text-transform:none;font-size:.85em">{esc(r.choice(["Primary", "Inbox", "All inboxes", "Today"]))}</div>'
    fab = f'<div style="position:absolute;right:1em;bottom:1em;background:var(--accent);color:#fff;border-radius:1em;padding:.9em 1.2em;box-shadow:0 4px 14px rgba(0,0,0,.3)" class="row g1 b">{ico("pencil", 1.3, "#fff")}Compose</div>'
    return search + lab + f'<div style="flex:1;min-height:0;overflow:hidden;position:relative">{"".join(rows)}{fab}</div>'


@family("email_view", web=0.3)
def fam_email_view(c: Ctx) -> str:
    r = c.r
    c.variant = "message"
    c.tab = None
    subj, prev = r.choice(EMAIL_SUBJECTS)
    co = r.choice(COMPANIES)
    subj = subj.format(n=c.digits(6), co=co)
    sd = r.choice([c.person(), co, "HDFC Bank Alerts", "no-reply@" + co.lower().replace(" ", "") + ".com"])
    d = c.date(100)
    amt = c.money(c.amount(200, 60000))
    paras = [
        f"Hi {r.choice(FIRST)},",
        f"{prev} {c.fmt_date(d, 'long')}. The reference for this message is {c.alnum(10)}.",
        r.choice([f"Amount: {amt}\nOrder ID: {c.digits(9)}\nPayment method: {r.choice(['Visa ending ' + c.digits(4), 'UPI', 'Net banking'])}",
                  f"Your one-time password is {c.digits(6)}. It is valid for 10 minutes. Do not share it with anyone.",
                  f"Invoice total: {amt}. Due date: {c.fmt_date(d + _dt.timedelta(days=15), 'dmy_mon')}.",
                  f"Flight {c.alnum(2)}{c.digits(3)} departs {c.time()} from {r.choice(CITIES)} to {r.choice(CITIES)}. PNR {c.alnum(6)}."]),
        "If you did not initiate this request, please contact our support team immediately or reply to this email.",
        f"Regards,\n{r.choice(FIRST)} {r.choice(LAST)}\n{co} Customer Care",
    ]
    ph = "".join(f'<p style="margin-bottom:.9em;line-height:1.45;white-space:pre-line">{esc(p)}</p>' for p in paras)
    top = (f'<div class="hdr" style="background:var(--bg)">{ico("back", 1.4)}<span class="grow"></span>{ico("trash", 1.3)}{ico("mail", 1.3)}{ico("vdots", 1.3)}</div>')
    head = (f'<div style="padding:.2em 1em .6em"><div style="font-size:{r.uniform(1.25, 1.6):.2f}em;font-weight:var(--fwb);line-height:1.25">{esc(subj)}</div>'
            f'<span class="pill" style="background:var(--bg2);color:var(--fg2);margin-top:.5em">Inbox</span></div>'
            f'<div class="row g2" style="padding:.5em 1em;align-items:flex-start">{avatar(c, sd, 2.8)}<div class="grow"><div class="row"><b class="grow ell">{esc(sd)}</b><span class="xs mu nw">{esc(c.fmt_date(d, "short"))}, {esc(c.time())}</span></div>'
            f'<div class="sm mu">to me {ico("down", .8)}</div></div>{ico("reply", 1.2)}</div>')
    btn = f'<div class="card" style="margin:.8em 1em;text-align:center"><div class="btn" style="display:inline-flex">{esc(r.choice(["View details", "Verify now", "Download invoice", "Track package"]))}</div></div>'
    return top + head + f'<div style="padding:.6em 1em;flex:1;min-height:0;overflow:hidden">{ph}{btn}</div><div class="row g2" style="padding:.7em 1em;border-top:1px solid var(--line)"><span class="btn o grow">{ico("reply", 1.1)}Reply</span><span class="btn o grow">{ico("share", 1.1)}Forward</span></div>'


@family("notifications", tall=0.2)
def fam_notif(c: Ctx) -> str:
    r = c.r
    var = r.choice(["lock", "lock", "shade"])
    c.variant = var
    c.tab = None
    c.sb_overlay = True
    h = c.hue
    wall = r.choice([
        f"linear-gradient({r.randint(140, 200)}deg,hsl({h} 70% 35%),hsl({h + 50} 75% 22%) 55%,hsl({h + 100} 70% 15%))",
        f"linear-gradient({r.randint(0, 360)}deg,hsl({h} 80% 62%),hsl({h + 60} 85% 50%))",
        f"radial-gradient(circle at 30% 20%,hsl({h + 40} 85% 60%),hsl({h} 70% 28%) 60%,#0b0b15)",
        "linear-gradient(160deg,#0f2027,#203a43 50%,#2c5364)"])
    light = c.dark is False and r.random() < .4
    if light:
        wall = f"linear-gradient({r.randint(140, 200)}deg,hsl({h} 70% 85%),hsl({h + 40} 70% 72%))"
    fgc = "#111" if light else "#fff"
    card_bg = "rgba(255,255,255,.62)" if light else "rgba(40,40,45,.55)" if r.random() < .5 else "rgba(255,255,255,.2)"
    c.sb_bg, c.sb_fg = "transparent", fgc
    n = c.n_rows(5.6, 2)
    cards = []
    for i in range(n):
        app, col = r.choice(APPS_N)
        kind = r.random()
        if kind < .3:
            title, body = c.person(), chat_line(c)
        elif kind < .55:
            title, body = r.choice(["Payment received", "Money debited", "UPI Payment Successful", "Transaction alert"]), f"{c.money(c.amount(50, 40000))} {r.choice(['credited to', 'debited from', 'paid to', 'received from'])} {r.choice([c.person(), c.merchant()])}. Ref {c.digits(12)}"
        elif kind < .75:
            title, body = r.choice(["Your OTP", "Verification code", "Login code"]), f"{c.digits(6)} is your one-time password for {app}. Valid for 10 minutes. Do not share."
        else:
            title, body = r.choice([f"{c.merchant()} order update", "Your ride is arriving", "Reminder: Meeting at 4:00 PM", "New sign-in detected", "Delivery today"]), r.choice(["Your order is out for delivery and arrives in 25 min.", "Driver is 2 minutes away. Share PIN " + c.digits(4), "Team standup in the main room", "Tap to review your account activity.", "Your package will be delivered by 9 PM."])
        age = r.choice(["now", f"{r.randint(1, 59)}m ago", c.time(), "Yesterday"])
        cards.append(f'<div style="background:{card_bg};backdrop-filter:blur(22px);border-radius:{r.choice([16, 20, 24])}px;padding:.75em .9em;display:flex;gap:.7em;align-items:flex-start;color:{fgc};box-shadow:0 2px 10px rgba(0,0,0,.12)">'
                     f'{app_icon(app, col, 2.3)}<div class="grow" style="min-width:0"><div class="row"><span class="xs grow" style="opacity:.75;text-transform:{"uppercase" if var == "shade" else "none"}">{esc(app)}</span><span class="xs" style="opacity:.75">{esc(age)}</span></div>'
                     f'<div class="b" style="margin-top:.1em">{esc(title)}</div><div class="sm" style="opacity:.9;line-height:1.3;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden">{esc(body)}</div></div></div>')
    d = c.date(30)
    hh, mm = r.randint(0, 23), r.randint(0, 59)
    clock = f"{(hh % 12) or 12}:{mm:02d}"
    top = (f'<div class="ctr" style="padding-top:calc(var(--sbh) + 1.4em);color:{fgc}"><div class="sm" style="opacity:.9">{esc(c.fmt_date(d, "wk"))}</div>'
           f'<div style="font-size:{r.uniform(3.6, 5.2):.2f}em;font-weight:var(--fwb);line-height:1.05;letter-spacing:-.02em">{clock}</div></div>')
    if var == "shade":
        top = (f'<div style="padding:calc(var(--sbh) + .6em) 1.2em .6em;color:{fgc}" class="row"><div style="font-size:2.6em;font-weight:var(--fw)">{clock}</div><span class="grow"></span><div class="sm r">{esc(c.fmt_date(d, "wk"))}<br>{esc(r.choice(CITIES))} {r.randint(18, 36)}°C</div></div>')
    return (f'<div style="position:absolute;inset:0;background:{wall}"></div><div style="position:relative;display:flex;flex-direction:column;flex:1;min-height:0">{top}'
            f'<div style="padding:1em .9em;display:flex;flex-direction:column;gap:.55em;flex:1;min-height:0;overflow:hidden">{"".join(cards)}</div></div>')


@family("crypto_wallet", web=0.25, tall=0.2)
def fam_crypto(c: Ctx) -> str:
    r = c.r
    c.variant = "wallet"
    c.tab = ([("home", "Home"), ("chart", "Markets"), ("swap", "Trade"), ("wallet", "Wallet"), ("user", "Me")], 3) if c.mobile else None
    coins = r.sample(COINS, len(COINS))
    n = min(len(coins), c.n_rows(4.2, 1))
    rows, total = [], 0.0
    for nm, sym, px, col in coins[:n]:
        px = px * r.uniform(.6, 1.5)
        qty = r.uniform(.2, 3) / (1 if px < 1 else px / 100) if px >= 1 else r.uniform(1e3, 5e5)
        qty = round(qty, 4 if px > 50 else 2)
        val = qty * px * (83 if c.cur["code"] == "INR" else 1)
        total += val
        ch = r.uniform(-9, 9)
        up = ch >= 0
        rows.append(f'<div class="li"><div class="av" style="width:2.6em;height:2.6em;border-radius:50%;background:{col};font-size:1em"><span style="font-size:1.05em">{esc(sym[:1])}</span></div>'
                    f'<div class="grow"><div class="b" style="font-weight:var(--fwb)">{esc(nm)}</div><div class="xs mu">{qty:,} {esc(sym)}</div></div>'
                    f'{spark(r, up, 56, 22, c.good if up else c.bad)}<div class="r nw"><div class="b">{esc(c.money(val))}</div><div class="xs {"good" if up else "bad"}">{"+" if up else ""}{ch:.2f}%</div></div></div>')
    ch = r.uniform(-6, 7)
    grad = hero_gradient(c)
    hero = (f'<div style="margin:.4em 1em;border-radius:calc(var(--r) + 6px);background:{grad};color:#fff;padding:1.2em"><div class="row sm" style="opacity:.85"><span class="grow">Total balance</span><span>{esc(r.choice(["Main Wallet", "Spot", "Portfolio"]))} {ico("down", .8, "#fff")}</span></div>'
            f'<div style="font-size:{r.uniform(2.2, 3):.2f}em;font-weight:var(--fwb);margin:.2em 0">{esc(c.money(total))}</div>'
            f'<span class="pill" style="background:rgba(255,255,255,.22)">{"+" if ch >= 0 else ""}{ch:.2f}% (24h)</span></div>')
    acts = "".join(f'<div class="col" style="align-items:center;gap:.3em;flex:1"><span class="chk" style="width:3em;height:3em;background:var(--accent);color:#fff">{ico(i, 1.4, "#fff")}</span><span class="xs">{l}</span></div>' for i, l in [("up", "Send"), ("downarrow", "Receive"), ("swap", "Swap"), ("plus", "Buy")])
    head = f'<div class="hdr" style="background:var(--bg)">{avatar(c, c.person(), 2)}<span class="grow ctr b">{esc(r.choice(["Wallet", "My Assets", "Portfolio"]))}</span>{ico("bell", 1.3)}</div>'
    return head + hero + f'<div class="row" style="padding:.8em .4em">{acts}</div><div class="row" style="padding:.2em 1em"><b class="grow">Assets</b><span class="sm" style="color:var(--accent-t)">Manage</span></div><div style="flex:1;min-height:0;overflow:hidden">{"".join(rows)}</div>'


@family("stock_portfolio", web=0.3, tall=0.15)
def fam_stocks(c: Ctx) -> str:
    r = c.r
    c.variant = "portfolio"
    c.tab = ([("home", "Watchlist"), ("chart", "Portfolio"), ("file", "Orders"), ("user", "Profile")], 1) if c.mobile else None
    pool = STOCKS_IN if c.region == "in" else STOCKS_US
    k = 1.0 if (c.region == "in" or c.cur["code"] != "INR") else 1
    n = c.n_rows(5.0, 1)
    rows, inv, cur = [], 0.0, 0.0
    for i in range(n):
        sym, px = pool[i % len(pool)]
        px *= r.uniform(.7, 1.4) * (1 if c.region == "in" else 1)
        q = r.randint(2, 200)
        avg = px * r.uniform(.6, 1.25)
        i_ = q * avg
        c_ = q * px
        inv += i_
        cur += c_
        pl = c_ - i_
        up = pl >= 0
        pc = pl / i_ * 100
        dch = r.uniform(-3, 3)
        rows.append(f'<div class="li" style="align-items:flex-start;flex-wrap:wrap;padding:.8em 1em"><div class="grow"><div class="b">{esc(sym)}</div><div class="xs mu">{q} Qty • Avg {esc(c.money(avg))}</div></div>'
                    f'{spark(r, dch >= 0, 50, 20, c.good if dch >= 0 else c.bad)}<div class="r nw"><div class="b {"good" if up else "bad"}">{esc(c.money(pl, sign=True))}</div><div class="xs mu">LTP {esc(c.money(px))} <span class="{"good" if dch >= 0 else "bad"}">({"+" if dch >= 0 else ""}{dch:.2f}%)</span></div></div></div>')
    pl = cur - inv
    up = pl >= 0
    ind = c.good if up else c.bad
    day = cur * r.uniform(-.02, .025)
    head = f'<div class="hdr" style="background:var(--bg)"><b class="grow" style="font-size:1.25em">{esc(r.choice(["Holdings", "Portfolio", "Investments"]))} ({n})</b>{ico("search", 1.3)}{ico("vdots", 1.3)}</div>'
    summ = (f'<div class="card" style="margin:.4em .8em"><div class="row"><div class="grow"><div class="xs mu">Invested</div><b>{esc(c.money(inv))}</b></div><div class="r"><div class="xs mu">Current</div><b>{esc(c.money(cur))}</b></div></div>'
            f'<div class="hr" style="margin:.7em 0"></div><div class="row"><div class="grow"><div class="xs mu">Total returns</div><b style="color:{ind};font-size:1.2em">{esc(c.money(pl, sign=True))}</b> <span class="sm" style="color:{ind}">({pl / inv * 100:+.2f}%)</span></div>'
            f'<div class="r"><div class="xs mu">1D returns</div><b class="{"good" if day >= 0 else "bad"}">{esc(c.money(day, sign=True))}</b></div></div></div>')
    return head + summ + f'<div style="flex:1;min-height:0;overflow:hidden;background:var(--card)">{"".join(rows)}</div>'


@family("ride_receipt", web=0.15)
def fam_ride(c: Ctx) -> str:
    r = c.r
    food = r.random() < .45
    c.variant = "food" if food else "ride"
    c.tab = None
    d = c.date(120)
    k = 1.0 if c.cur["code"] == "INR" else 0.045
    if food:
        shop = r.choice(["Burger Barn", "Spice Route", "Pizza Palace", "Green Bowl", "Taco Town", "Dosa Corner", "Sushi Zen", "Biryani Blues", "The Cafe", "Noodle House"])
        its = r.sample(FOODS, r.randint(2, 4))
        sub = 0.0
        lines = ""
        for nm, p in its:
            q = r.choice([1, 1, 2])
            pr = round(p * k, 2) * q
            sub += pr
            lines += f'<div class="row g2" style="padding:.35em 0"><span class="chk" style="width:.9em;height:.9em;border-radius:2px;border:2px solid {c.good};background:transparent;flex:none"><i style="width:.38em;height:.38em;border-radius:50%;background:{c.good};display:block"></i></span><span class="grow">{q} x {esc(nm)}</span><span>{esc(c.money(pr))}</span></div>'
        fees = [("Delivery fee", round(r.uniform(15, 60) * k, 2)), ("Platform fee", round(r.uniform(3, 10) * k, 2)), ("Taxes & charges", round(sub * r.uniform(.05, .12), 2))]
        disc = round(sub * r.uniform(.1, .3), 2) if r.random() < .5 else 0
        total = sub + sum(f for _, f in fees) - disc
        frows = "".join(f'<div class="row sm" style="padding:.22em 0"><span class="grow mu">{esc(k_)}</span><span>{esc(c.money(v))}</span></div>' for k_, v in fees)
        if disc:
            frows += f'<div class="row sm good" style="padding:.22em 0"><span class="grow">Coupon discount</span><span>-{esc(c.money(disc))}</span></div>'
        title = shop
        head = (f'<div style="padding:1em;background:{hero_gradient(c)};color:#fff"><div class="xs" style="opacity:.85">ORDER #{c.digits(10)}</div><div class="b" style="font-size:1.4em">{esc(shop)}</div>'
                f'<div class="sm" style="opacity:.9">{esc(r.choice(PLACES))} • Delivered {esc(c.fmt_date(d, "mon_dmy"))}, {esc(c.time())}</div></div>')
        body = (f'<div class="card" style="margin:.8em"><div class="b" style="margin-bottom:.4em">Your order</div>{lines}<div class="hr" style="margin:.6em 0"></div>'
                f'<div class="row sm" style="padding:.22em 0"><span class="grow mu">Item total</span><span>{esc(c.money(sub))}</span></div>{frows}<div class="hr" style="margin:.6em 0"></div>'
                f'<div class="row b lg"><span class="grow">Bill total</span><span>{esc(c.money(total))}</span></div><div class="xs mu" style="margin-top:.3em">Paid via {esc(r.choice(["UPI", "Card", "Wallet", "Cash"]))}</div></div>')
        body += (f'<div class="card" style="margin:.8em"><div class="b" style="margin-bottom:.3em">Delivery partner</div><div class="row g2">{avatar(c, c.person(), 2.6)}<div class="grow"><div>{esc(c.person())}</div><div class="xs mu">Rated {r.uniform(4, 5):.1f} ★</div></div>{ico("phone", 1.3, "var(--accent-t)")}</div></div>')
        return f'<div class="hdr">{ico("back", 1.4)}<b class="grow">Order Summary</b>{ico("file", 1.3)}</div>{head}<div style="flex:1;min-height:0;overflow:hidden;background:var(--bg2)">{body}</div>'
    dist = r.uniform(1.5, 24)
    base = round(r.uniform(30, 90) * k, 2)
    dst = round(dist * r.uniform(8, 14) * k, 2)
    tm = round(r.uniform(.5, 2) * dist * k, 2)
    fare = [("Base fare", base), (f"Distance ({dist:.1f} km)", dst), (f"Time ({int(dist * r.uniform(2, 4))} min)", tm), ("Booking fee", round(r.uniform(5, 25) * k, 2)), ("Taxes", round((base + dst + tm) * .05, 2))]
    disc = round(r.uniform(10, 80) * k, 2) if r.random() < .4 else 0
    total = sum(v for _, v in fare) - disc
    frows = "".join(f'<div class="row" style="padding:.3em 0"><span class="grow mu">{esc(k_)}</span><span>{esc(c.money(v))}</span></div>' for k_, v in fare)
    if disc:
        frows += f'<div class="row good" style="padding:.3em 0"><span class="grow">Promo applied</span><span>-{esc(c.money(disc))}</span></div>'
    rid = r.choice(["Auto", "Mini", "Prime Sedan", "UberX", "Comfort", "Bike", "SUV"])
    h = r.randint(0, 360)
    pts = " ".join(f"{x:.0f},{y:.0f}" for x, y in [(20, 100), (60, 60 + r.randint(-20, 20)), (110, 90 + r.randint(-25, 10)), (160, 40 + r.randint(-10, 20)), (230, 55 + r.randint(-15, 15)), (290, 22)])
    mp = (f'<div style="height:{min(11, 8 + c.W / 300):.1f}em;background:linear-gradient(120deg,hsl({h} 25% {82 if not c.dark else 22}%),hsl({h + 20} 22% {90 if not c.dark else 28}%));position:relative;overflow:hidden">'
          f'<svg viewBox="0 0 310 120" preserveAspectRatio="none" style="position:absolute;inset:0;width:100%;height:100%"><g stroke="{"rgba(255,255,255,.7)" if not c.dark else "rgba(255,255,255,.12)"}" stroke-width="7" fill="none"><path d="M0 30L310 70M60 0L120 120M200 0L240 120M0 95L310 100"/></g>'
          f'<polyline points="{pts}" fill="none" stroke="{"#111" if not c.dark else "#fff"}" stroke-width="3" stroke-linejoin="round"/><circle cx="20" cy="100" r="6" fill="{c.accent}"/><rect x="284" y="16" width="12" height="12" fill="#111"/></svg></div>')
    return (f'<div class="hdr">{ico("back", 1.4)}<b class="grow">Trip details</b>{ico("vdots", 1.3)}</div>{mp}'
            f'<div style="padding:.9em 1em"><div class="row"><div class="grow"><div class="mu sm">{esc(c.fmt_date(d, "wk"))}, {esc(c.time())}</div><div class="b" style="font-size:1.35em">Thanks for riding, {esc(r.choice(FIRST))}</div></div></div>'
            f'<div style="font-size:{r.uniform(2.2, 3):.2f}em;font-weight:var(--fwb);margin:.3em 0">{esc(c.money(total))}</div>'
            f'<div class="row g2" style="margin:.6em 0"><span style="width:.7em;height:.7em;border-radius:50%;background:var(--accent);flex:none"></span><span class="grow sm ell">{esc(r.choice(PLACES))}</span><span class="xs mu">{esc(c.time())}</span></div>'
            f'<div class="row g2"><span style="width:.7em;height:.7em;background:var(--fg);flex:none"></span><span class="grow sm ell">{esc(r.choice(PLACES))}</span><span class="xs mu">{esc(c.time())}</span></div></div>'
            f'<div class="card" style="margin:0 1em .8em"><div class="row g2" style="margin-bottom:.6em">{avatar(c, c.person(), 2.6)}<div class="grow"><div class="b">{esc(c.person())}</div><div class="xs mu">{esc(rid)} • KA {c.digits(2)} {c.alnum(2)} {c.digits(4)} • {r.uniform(4.3, 5):.2f} ★</div></div></div>'
            f'<div class="hr" style="margin-bottom:.5em"></div>{frows}<div class="hr" style="margin:.5em 0"></div><div class="row b lg"><span class="grow">Total</span><span>{esc(c.money(total))}</span></div>'
            f'<div class="xs mu" style="margin-top:.4em">Paid via {esc(r.choice(["UPI", "Cash", "Visa •••• " + c.digits(4), "Wallet"]))} • Trip ID {esc(c.alnum(12))}</div></div>')


@family("desktop_dashboard", desktop=True)
def fam_dashboard(c: Ctx) -> str:
    r = c.r
    c.variant = "dashboard"
    co = r.choice(COMPANIES)
    c.url = f"app.{co.lower().replace(' ', '')}.com/dashboard"
    c.title = f"{co} - Dashboard"
    sw = int(min(250, max(170, c.W * .17)))
    nav = [("home", "Overview"), ("chart", "Analytics"), ("card", "Payments"), ("user", "Customers"), ("file", "Invoices"), ("gear", "Settings")]
    navh = "".join(f'<div class="row g2" style="padding:.65em .8em;border-radius:.6em;margin-bottom:.15em;{"background:var(--accent);color:#fff;font-weight:var(--fwb)" if i == (c.W % 3) else "color:var(--fg2)"}">{ico(ic, 1.15)}<span>{esc(lb)}</span></div>' for i, (ic, lb) in enumerate(nav))
    side = (f'<aside style="width:{sw}px;flex:none;background:var(--card);border-right:1px solid var(--line);padding:1em .8em"><div class="row g2" style="padding:.2em .4em 1.2em"><span class="chk" style="width:1.9em;height:1.9em;border-radius:.5em;background:var(--accent);color:#fff;font-weight:700">{esc(co[0])}</span><b class="lg">{esc(co)}</b></div>{navh}</aside>')
    stats = [("Total Revenue", c.money(c.amount(20000, 900000), dec=False)), ("Active Users", f"{r.randint(800, 90000):,}"), ("Orders", f"{r.randint(120, 9000):,}"), ("Conversion", f"{r.uniform(1.2, 9):.2f}%")]
    ncol = 4 if c.W >= 1200 else 3
    sh = ""
    for lb, v in stats[:ncol]:
        ch = r.uniform(-12, 18)
        sh += (f'<div class="card" style="padding:.9em 1em"><div class="mu sm">{esc(lb)}</div><div style="font-size:1.9em;font-weight:var(--fwb);margin:.15em 0">{esc(v)}</div>'
               f'<div class="sm {"good" if ch >= 0 else "bad"}">{"▲" if ch >= 0 else "▼"} {abs(ch):.1f}% <span class="mu">vs last month</span></div></div>')
    bars = "".join(f'<rect x="{i * 28 + 8}" y="{110 - hv}" width="16" height="{hv}" rx="3" fill="{c.accent}" opacity="{.45 + .5 * (i == 9)}"/><text x="{i * 28 + 16}" y="126" font-size="9" text-anchor="middle" fill="currentColor" opacity=".6">{MONTHS[i]}</text>' for i, hv in enumerate([r.randint(25, 100) for _ in range(12)]))
    chart = f'<div class="card" style="padding:1em"><div class="b" style="margin-bottom:.5em">Revenue overview</div><svg viewBox="0 0 345 132" style="width:100%;height:{max(10, 14 - c.fs / 4):.0f}em;display:block">{bars}</svg></div>'
    n = max(5, int((c.H - 380) / (c.fs * 3.0)) + 2)
    stt = {"Paid": ("#16a34a", "rgba(22,163,74,.14)"), "Pending": ("#d97706", "rgba(217,119,6,.15)"), "Failed": ("#dc2626", "rgba(220,38,38,.14)"), "Refunded": ("#6366f1", "rgba(99,102,241,.14)")}
    trs = ""
    for _ in range(n):
        s = wchoice(r, list(stt), [6, 3, 1, 1])
        nm = c.person()
        trs += (f'<tr><td class="b" style="font-weight:var(--fw)">#{c.digits(6)}</td><td><div class="row g2">{avatar(c, nm, 1.9)}{esc(nm)}</div></td><td class="mu">{esc(c.fmt_date(c.date(60), "mon_dmy"))}</td><td>{esc(r.choice(["Visa", "UPI", "Mastercard", "PayPal", "Net Banking"]))}</td>'
                f'<td><span class="pill" style="color:{stt[s][0]};background:{stt[s][1]}">{s}</span></td><td class="n b">{esc(c.money(c.amount(200, 90000)))}</td></tr>')
    tbl = (f'<div class="card" style="padding:.9em 1em;flex:1;min-height:0;overflow:hidden"><div class="row" style="margin-bottom:.5em"><b class="grow">Recent transactions</b><span class="sm" style="color:var(--accent-t)">View all</span></div>'
           f'<table class="tbl"><thead><tr><th>Order</th><th>Customer</th><th>Date</th><th>Method</th><th>Status</th><th class="n">Amount</th></tr></thead><tbody>{trs}</tbody></table></div>')
    top = (f'<div class="row g2" style="padding:.7em 1.3em;background:var(--card);border-bottom:1px solid var(--line)"><div class="grow row g2" style="background:var(--bg2);border-radius:.6em;padding:.55em .9em;max-width:26em;color:var(--fg2)">{ico("search", 1.1)}Search...</div><span class="grow"></span>{ico("bell", 1.3)}{avatar(c, c.person(), 2.1)}</div>')
    main = (f'<main style="flex:1;min-width:0;display:flex;flex-direction:column;background:var(--bg2)">{top}<div style="padding:1.1em 1.3em;display:flex;flex-direction:column;gap:1em;flex:1;min-height:0;overflow:hidden">'
            f'<div class="row"><b style="font-size:1.5em" class="grow">{esc(r.choice(["Dashboard", "Overview", "Sales"]))}</b><span class="btn" style="padding:.5em 1em">{esc(r.choice(["Export", "New invoice", "Download report"]))}</span></div>'
            f'<div style="display:grid;grid-template-columns:repeat({ncol},1fr);gap:1em">{sh}</div>{chart if c.H > 700 else ""}{tbl}</div></main>')
    return f'<div style="display:flex;height:100%">{side}{main}</div>'


@family("desktop_invoice", desktop=True)
def fam_invoice(c: Ctx) -> str:
    r = c.r
    c.variant = "invoice"
    co = r.choice(COMPANIES)
    cli = r.choice([x for x in COMPANIES if x != co])
    c.url = f"billing.{co.lower().replace(' ', '')}.com/invoices/INV-{c.digits(5)}"
    c.title = f"Invoice - {co}"
    k = 1.0 if c.cur["code"] == "INR" else 0.045
    n = r.randint(3, 7)
    sub = 0.0
    trs = ""
    for i in range(n):
        desc = r.choice(["Website design", "Hosting (annual)", "Consulting hours", "Mobile app development", "SEO optimisation", "Support plan", "Cloud storage 1TB", "Logo & branding", "Data migration", "API integration", "Training workshop", "Domain renewal"])
        q = r.randint(1, 20)
        rate = round(r.randint(5, 80) * 100 * k, 2)
        amt = q * rate
        sub += amt
        trs += f'<tr><td>{i + 1}</td><td>{esc(desc)}</td><td class="n">{q}</td><td class="n">{esc(c.money(rate))}</td><td class="n b">{esc(c.money(amt))}</td></tr>'
    taxr = r.choice([5, 8, 10, 12, 18])
    tax = round(sub * taxr / 100, 2)
    total = sub + tax
    d = c.date(100)
    paper = (f'<div style="background:#fff;color:#111;max-width:{min(c.W - 160, 900)}px;margin:1.2em auto;padding:2.2em 2.4em;border-radius:6px;box-shadow:0 4px 24px rgba(0,0,0,.18);font-size:.95em">'
             f'<div class="row" style="align-items:flex-start"><div class="grow"><div class="row g2"><span class="chk" style="width:2.6em;height:2.6em;border-radius:.6em;background:{c.accent};color:#fff;font-weight:700;font-size:1.1em">{esc(co[0])}</span><b style="font-size:1.4em">{esc(co)}</b></div>'
             f'<div style="color:#666;margin-top:.5em;font-size:.88em;line-height:1.5">{r.randint(1, 999)} {esc(r.choice(["Business Park", "Main Street", "Innovation Drive"]))}<br>{esc(r.choice(CITIES))}, {c.digits(6)}<br>GSTIN: {c.digits(2)}{c.alnum(5)}{c.digits(4)}{c.alnum(1)}1Z{c.digits(1)}</div></div>'
             f'<div class="r"><div style="font-size:2em;font-weight:800;letter-spacing:.04em;color:{c.accent}">INVOICE</div><div style="color:#444;margin-top:.3em">#INV-{c.digits(5)}</div>'
             f'<div style="margin-top:.5em;display:inline-block;padding:.2em .8em;border-radius:99px;background:{"#e6f4ea" if r.random() < .6 else "#fff4e5"};color:{"#137333" if r.random() < .6 else "#b45309"};font-weight:700;font-size:.8em">{esc(r.choice(["PAID", "DUE", "PAID", "OVERDUE"]))}</div></div></div>'
             f'<div class="row" style="margin:1.6em 0 1.2em;gap:3em;align-items:flex-start"><div><div style="color:#888;font-size:.78em;text-transform:uppercase">Billed to</div><b>{esc(cli)}</b><div style="color:#555;font-size:.9em">{esc(c.person())}<br>{esc(r.choice(CITIES))}</div></div>'
             f'<div><div style="color:#888;font-size:.78em;text-transform:uppercase">Issue date</div><b>{esc(c.fmt_date(d, "mon_dmy"))}</b></div><div><div style="color:#888;font-size:.78em;text-transform:uppercase">Due date</div><b>{esc(c.fmt_date(d + _dt.timedelta(days=r.choice([7, 15, 30])), "mon_dmy"))}</b></div></div>'
             f'<table class="tbl" style="color:#111"><thead><tr><th style="color:#666">#</th><th style="color:#666">Description</th><th class="n" style="color:#666">Qty</th><th class="n" style="color:#666">Rate</th><th class="n" style="color:#666">Amount</th></tr></thead><tbody>{trs}</tbody></table>'
             f'<div style="margin-left:auto;width:min(100%,19em);margin-top:1em"><div class="row" style="padding:.3em 0"><span class="grow" style="color:#666">Subtotal</span><span>{esc(c.money(sub))}</span></div><div class="row" style="padding:.3em 0"><span class="grow" style="color:#666">Tax ({taxr}%)</span><span>{esc(c.money(tax))}</span></div>'
             f'<div class="row" style="padding:.6em 0;border-top:2px solid #111;margin-top:.3em;font-size:1.2em"><b class="grow">Total</b><b>{esc(c.money(total))}</b></div></div>'
             f'<div style="margin-top:1.2em;color:#666;font-size:.85em;line-height:1.5">Bank: {esc(c.bank())} • A/c {c.digits(12)} • Please include invoice number in the payment reference. Thank you for your business.</div></div>')
    return f'<div style="height:100%;overflow:hidden;background:{"#2b2d31" if c.dark else "#e9ecef"}">{paper}</div>'


# ----------------------------------------------------------------------------
# Image assembly
# ----------------------------------------------------------------------------
FAMILY_NAMES = ["chat", "group_chat", "upi_receipt", "bank_balance", "bank_statement", "ecom_order", "social_post",
                "email_inbox", "email_view", "notifications", "sms_otp", "crypto_wallet", "stock_portfolio",
                "ride_receipt", "desktop_dashboard", "desktop_invoice"]
MOBILE_VP = [(390, 844), (412, 915), (360, 800), (430, 932), (375, 667)]
MOBILE_VP_W = [30, 22, 22, 18, 8]
TALL_VP = [(390, 1200), (412, 1200), (360, 1280), (375, 1100), (430, 1250), (390, 1400)]
DESKTOP_VP = [(1280, 800), (1440, 900), (1024, 768)]
DESKTOP_VP_W = [45, 35, 20]


def pick_scale(r: random.Random, w: int, h: int, mobile: bool, max_long: int) -> int:
    opts = [1, 2, 3]
    wts = [.05, .475, .475] if mobile else [.6, .4, 0.0]
    ok = [(o, wt) for o, wt in zip(opts, wts) if max(w, h) * o <= max_long]
    if not ok:
        return 1
    ws = [wt for _, wt in ok]
    if sum(ws) == 0:
        ws = [1] * len(ok)
    return wchoice(r, [o for o, _ in ok], ws)


def build_page(seed: int, index: int, families: list[str] | None = None, max_long: int = MAX_LONG_SIDE) -> tuple[str, dict]:
    """Return (html, meta) for image `index` under base `seed`. Fully deterministic."""
    pseed = seed * 100003 + index
    r = random.Random(pseed)
    fams = families or FAMILY_NAMES
    fam = fams[index % len(fams)]
    spec = FAMILIES[fam]
    desktop = spec["desktop_only"] or (r.random() < spec["web_prob"])
    if desktop:
        W, H = wchoice(r, DESKTOP_VP, DESKTOP_VP_W)
        tall = False
    else:
        tall = r.random() < spec["tall_prob"]
        W, H = r.choice(TALL_VP) if tall else wchoice(r, MOBILE_VP, MOBILE_VP_W)
    mobile = not desktop
    scale = pick_scale(r, W, H, mobile, max_long)
    c = Ctx(r, W, H, mobile, fam)
    c.tab, c.sb_overlay, c.av_shape = None, False, r.choice(["circle", "circle", "squircle", "rounded"])
    c.sb_kind = r.choice(["ios", "ios", "android"])
    c.sb_island = c.sb_kind == "ios" and r.random() < .5 and H >= 800 and W >= 390
    c.url, c.title = "", ""
    dark = r.random() < 0.42
    make_theme(c, dark)
    flabel, fstack, _, fbucket = pick_font(r)
    # sizes: mobile 12..24 mostly, rare large; desktop 12..18
    if mobile:
        base = wchoice(r, [12, 13, 14, 15, 16, 17, 18, 19, 20, 22, 24, 28, 32], [4, 6, 10, 12, 16, 12, 10, 6, 6, 5, 4, 2, 1])
        if scale == 1:
            base = max(base, 16)
        if fam == "bank_statement":
            base = min(max(base, 15), 16)
        if W <= 375 and base > 20:
            base = 18
    else:
        base = wchoice(r, [11, 12, 13, 14, 15, 16, 17, 18, 20], [2, 6, 10, 14, 12, 12, 6, 4, 2])
        if scale == 1:
            base = max(base, 13)
        if spec["desktop_only"]:
            base = max(base, 14 if scale == 2 else 14)
        else:
            base = max(base, 15)  # responsive-web column layouts: keep text legible
    if fbucket == "mono":
        base = max(11, base - 2)
    fw = r.choice([300, 400, 400, 400, 400, 500])
    fwb = r.choice([600, 700, 700, 700, 800])
    if fbucket == "mono":
        fw = 400
    c.vars.update({
        "--W": f"{W}px", "--H": f"{H}px", "--ff": fstack, "--fs": f"{base}px", "--fw": str(fw), "--fwb": str(fwb),
        "--lh": r.choice(["1.25", "1.3", "1.35", "1.4"]), "--ls": r.choice(["0", "0", "0", "-0.01em", "0.01em", "0.02em"]),
        "--sbh": "0px", "--tbh": "0px", "--colw": "100%",
    })
    if mobile:
        c.vars["--sbh"] = ("54px" if c.sb_island else "46px" if c.sb_kind == "ios" else "30px")
    inner = spec["fn"](c)
    v = c.vars
    if mobile:
        has_tab = c.tab is not None
        if has_tab:
            labels, on = c.tab
            v["--tbh"] = "82px" if c.sb_kind == "ios" else "64px"
        sbar = status_bar(c)
        if c.sb_overlay:
            sbar = sbar.replace('class="sb"', 'class="sb" data-ov="1"', 1).replace('style="', 'style="position:absolute;left:0;right:0;top:0;', 1)
        tb = tab_bar(c, labels, on) if has_tab else ""
        body = f'<div class="screen">{sbar}<div class="app">{inner}</div>{tb}</div>'
    else:
        if spec["desktop_only"]:
            if r.random() < 0.7:
                body = f'<div class="screen">{browser_frame(c, c.url, c.title, inner)}</div>'
            else:
                body = f'<div class="screen"><div style="height:100%;width:100%;overflow:hidden">{inner}</div></div>'
        else:
            colw = r.choice([560, 640, 760, 900, 1000])
            colw = min(colw, W - 120)
            v["--colw"] = f"{colw}px"
            dom = r.choice(["web.", "app.", "my.", ""]) + r.choice(["swiftpay", "kartify", "finbank", "chatly", "mailbox", "tradehub", "coinvault", "quickride", "socialsphere"]) + r.choice([".com", ".in", ".io", ".co"])
            path = "/" + fam.replace("_", "-")
            inner = f'<div class="web">{inner}</div>'
            body = f'<div class="screen">{browser_frame(c, dom + path, dom.split(".")[-2].title() if "." in dom else dom, inner)}</div>'
            c.vars["--bg2"] = c.vars["--bg2"]
    root = ";".join(f"{k}:{val}" for k, val in v.items())
    page = (f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width={W}">'
            f'<title>{esc(fam)}</title><style>:root{{{root}}}{BASE_CSS}'
            f'{".bpage{background:var(--bg2)}" if (desktop and not spec["desktop_only"]) else ""}</style></head><body>{body}</body></html>')
    meta = {"family": fam, "font_family": flabel, "theme": "dark" if dark else "light", "viewport": [W, H], "scale": scale,
            "seed": pseed, "index": index, "base_seed": seed, "variant": c.variant, "base_fs": base, "currency": c.cur["code"],
            "tall": tall, "desktop": desktop}
    return page, meta


# ----------------------------------------------------------------------------
# Batch rendering
# ----------------------------------------------------------------------------
_W: dict = {}


def _worker_init(tmp_root: str, chrome: str, max_long: int, families, keep_html: bool):
    wd = os.path.join(tmp_root, f"w{os.getpid()}")
    os.makedirs(wd, exist_ok=True)
    _W.update(dir=wd, chrome=chrome, max_long=max_long, families=families, keep_html=keep_html, n=0)


def _render_job(args):
    seed, index, png_path, img_id = args
    html_text, meta = build_page(seed, index, _W["families"], _W["max_long"])
    wd = _W["dir"]
    hp = os.path.join(wd, f"{img_id}.html")
    Path(hp).write_text(html_text, encoding="utf-8")
    W, H = meta["viewport"]
    tmp_png = os.path.join(wd, f"{img_id}.png")
    ok = False
    for attempt in range(3):
        udir = os.path.join(wd, f"profile{'' if attempt == 0 else attempt}")
        if os.path.exists(tmp_png):
            os.remove(tmp_png)
        ok = _run_chrome(_W["chrome"], udir, hp, tmp_png, W, H, meta["scale"])
        if ok:
            try:
                from PIL import Image
                with Image.open(tmp_png) as im:
                    ok = im.size[0] >= W * meta["scale"] * 0.95 and im.size[1] >= H * meta["scale"] * 0.95
                    meta["pixels"] = list(im.size)
            except ImportError:
                pass
            except Exception:
                ok = False
        if ok:
            break
        shutil.rmtree(udir, ignore_errors=True)
    if not ok:
        return {"index": index, "error": "render failed", **meta}
    os.makedirs(os.path.dirname(png_path), exist_ok=True)
    shutil.move(tmp_png, png_path)
    if _W["keep_html"]:
        shutil.copy(hp, png_path[:-4] + ".html")
    os.remove(hp)
    meta.update(id=img_id, path=png_path)
    return meta


def render_batch(out_dir, n: int, seed: int = 0, workers: int = 8, families: list[str] | None = None,
                 max_long: int = MAX_LONG_SIDE, keep_html: bool = False, start_index: int = 0,
                 progress: bool = True) -> list[dict]:
    """Render ``n`` images into ``out_dir/chrome`` and append to ``out_dir/chrome_manifest.jsonl``.

    Returns the manifest rows (sorted by index). Deterministic for a given (seed, n, start_index).
    """
    out_dir = Path(out_dir).resolve()
    (out_dir / "chrome").mkdir(parents=True, exist_ok=True)
    chrome = find_chrome()
    tmp_root = tempfile.mkdtemp(prefix="render_chrome_")
    jobs = []
    for i in range(start_index, start_index + n):
        img_id = f"chrome_s{seed}_{i:05d}"
        jobs.append((seed, i, str(out_dir / "chrome" / f"{img_id}.png"), img_id))
    rows: list[dict] = []
    failed: list[dict] = []
    t0 = time.time()
    try:
        workers = max(1, int(workers))
        with cf.ProcessPoolExecutor(max_workers=workers, initializer=_worker_init,
                                    initargs=(tmp_root, chrome, max_long, families, keep_html)) as ex:
            for k, res in enumerate(ex.map(_render_job, jobs, chunksize=1), 1):
                (failed if "error" in res else rows).append(res)
                if progress and (k % 25 == 0 or k == len(jobs)):
                    el = time.time() - t0
                    print(f"[render_chrome] {k}/{len(jobs)}  {k / el * 60:.0f} img/min", file=sys.stderr, flush=True)
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
    rows.sort(key=lambda d: d["index"])
    with open(out_dir / "chrome_manifest.jsonl", "a", encoding="utf-8") as f:
        for d in rows:
            f.write(json.dumps({k: d[k] for k in ("id", "path", "family", "font_family", "theme", "viewport", "scale", "seed")} |
                               {k: d[k] for k in d if k not in ("id", "path", "family", "font_family", "theme", "viewport", "scale", "seed")}) + "\n")
    if failed:
        print(f"[render_chrome] WARNING: {len(failed)} images failed: {[d['index'] for d in failed][:20]}", file=sys.stderr)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=False, help="output dir (writes DIR/chrome/*.png + DIR/chrome_manifest.jsonl)")
    ap.add_argument("--count", type=int, default=60)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=min(10, os.cpu_count() or 4))
    ap.add_argument("--families", default=None, help="comma-separated subset of: " + ",".join(FAMILY_NAMES))
    ap.add_argument("--max-long", type=int, default=MAX_LONG_SIDE, help="cap on the PNG long side in device px")
    ap.add_argument("--start-index", type=int, default=0)
    ap.add_argument("--keep-html", action="store_true", help="also save the HTML next to each PNG")
    ap.add_argument("--verify-fonts", action="store_true", help="probe which FONTS resolve in this Chrome and exit")
    a = ap.parse_args(argv)
    if a.verify_fonts:
        res = verify_fonts()
        for k, v in res.items():
            print(f"{'OK  ' if v else 'MISS'} {k}")
        return 0
    if not a.out:
        ap.error("--out is required")
    fams = a.families.split(",") if a.families else None
    if fams:
        bad = [f for f in fams if f not in FAMILIES]
        if bad:
            ap.error(f"unknown families: {bad}")
    t0 = time.time()
    rows = render_batch(a.out, a.count, a.seed, a.workers, fams, a.max_long, a.keep_html, a.start_index)
    el = time.time() - t0
    print(f"rendered {len(rows)}/{a.count} images in {el:.1f}s ({len(rows) / el * 60:.0f} img/min) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
