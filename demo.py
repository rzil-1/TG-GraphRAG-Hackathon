import requests

host = "https://tg-f2cb6617-bdd7-4a92-87a6-01fbbe9fc39d.tg-3452941248.i.tgcloud.io"

# Try the plain HTTP ping — no auth needed
try:
    r = requests.get(f"{host}:14240", timeout=10)
    print("Status:", r.status_code)
    print("Body:", r.text[:300])
except Exception as e:
    print("Failed:", e)