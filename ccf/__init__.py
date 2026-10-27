"""clear-creek-call-forecast: forecasting the controlling call on Clear
Creek (Colorado Division 1, Water District 7) from the truth table
hydrohistorian.com publishes, scored by the rules the site scores by.

Start at docs/TARGET.md. The site's contract is schema/call_forecast.schema.json.
"""
__version__ = "0.1.0"

SLUG = "d1_wd7_clear_creek"
BASIN = "clear_creek"
SITE = "https://hydrohistorian.com"
TRUTH_URL = f"{SITE}/static/data/releases/call_truth/{BASIN}/"
DIV1_URL = f"{SITE}/static/data/releases/div1/"
ASSET_NAME = f"call_forecast_{SLUG}.json"
