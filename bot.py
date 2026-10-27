"""Pemantau posisi LP Meteora (DLMM) -> notifikasi Telegram.

Hanya BACA data publik berdasarkan alamat wallet. Tidak butuh private key.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

WALLET = os.environ["WALLET_ADDRESS"].strip()
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"].strip()
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"].strip()
# "true" = hanya kirim pesan kalau ada posisi OOR. "false" = kirim status tiap kali.
ONLY_ALERT = os.environ.get("ONLY_ALERT", "false").strip().lower() == "true"

API = "https://dlmm.datapi.meteora.ag/portfolio/open"


def get_json(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": "lp-monitor/1.0", "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def send(text):
    data = urllib.parse.urlencode(
        {"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": "true"}
    ).encode()
    urllib.request.urlopen(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=data, timeout=30
    ).read()


def fetch_pools():
    pools, page = [], 1
    while True:
        q = urllib.parse.urlencode({"user": WALLET, "page": page, "page_size": 50})
        d = get_json(f"{API}?{q}")
        pools += d.get("pools", [])
        if not d.get("hasNext"):
            return pools
        page += 1


def usd(x):
    try:
        return f"${float(x):,.2f}"
    except (TypeError, ValueError):
        return "-"


def main():
    wib = datetime.now(timezone(timedelta(hours=7))).strftime("%d/%m %H:%M WIB")
    try:
        pools = fetch_pools()
    except Exception as e:  # noqa: BLE001
        send(f"⚠️ Gagal cek posisi Meteora ({wib}): {e}")
        return

    if not pools:
        if False:
            send(f"📭 Tidak ada posisi DLMM yang terbuka ({wib}).")
        return

    lines, any_oor = [], False
    for p in pools:
        total = int(p.get("openPositionCount") or 0)
        oor = len(p.get("positionsOutOfRange") or [])
        if oor > 0:
            any_oor = True
            status = f"🔴 OOR ({oor} dari {total} posisi)"
        elif p.get("outOfRange") is None:
            status = "⚪ Status belum bisa dipastikan"
        else:
            status = "🟢 In range"
        lines.append(
            f"{p.get('tokenX')}/{p.get('tokenY')}\n"
            f"{status}\n"
            f"Nilai {usd(p.get('balances'))} | PnL {usd(p.get('pnl'))} "
            f"| Fee belum diklaim {usd(p.get('unclaimedFees'))}"
        )

    if ONLY_ALERT and not any_oor:
        return

    head = "🚨 ADA POSISI OOR!" if any_oor else "✅ Semua posisi in range"
    send(f"{head}\n📊 LP Meteora - {wib}\n\n" + "\n\n".join(lines))


if __name__ == "__main__":
    main()
    sys.exit(0)
