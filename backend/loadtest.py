"""Yengil yuklama testi — ilova qanchalik tez javob berayotganini o'lchaydi.

DIQQAT — shared hosting haqida
------------------------------
cPanel/CloudLinux akkauntida CPU, xotira va jarayonlar soni cheklangan (LVE).
Kuchli yuklama testi ilovaning emas, xostingning chegarasini ko'rsatadi va
akkauntni vaqtincha sekinlashtirib qo'yishi mumkin. Shuning uchun bu skript
ATAYIN kamtarona: sukut bo'yicha 5 ta parallel so'rov.

Ishlatish:

    python loadtest.py                          # lokal, 127.0.0.1
    python loadtest.py --host smart-kassa.uz    # Host sarlavhasi bilan
    python loadtest.py --users 10 --requests 20

Skript hech narsani o'zgartirmaydi — faqat O'QISH endpointlarini chaqiradi.
"""
from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parent / ".env")


async def timed(client: httpx.AsyncClient, method: str, path: str, **kw):
    started = time.perf_counter()
    try:
        response = await client.request(method, path, **kw)
        return (time.perf_counter() - started) * 1000, response.status_code
    except Exception as exc:  # noqa: BLE001
        return (time.perf_counter() - started) * 1000, f"XATO: {type(exc).__name__}"


def report(label: str, samples: list[float], codes: list) -> bool:
    good = [c for c in codes if isinstance(c, int) and c < 400]
    bad = [c for c in codes if c not in good]
    if not samples:
        print(f"  {label:22s} natija yo'q")
        return False

    ordered = sorted(samples)
    p50 = statistics.median(ordered)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    flag = "OK  " if not bad else "XATO"
    print(f"  {flag} {label:22s} p50 {p50:7.0f} ms | p95 {p95:7.0f} ms | "
          f"max {ordered[-1]:7.0f} ms | {len(good)}/{len(codes)} muvaffaqiyatli")
    if bad:
        print(f"       xatolar: {sorted(set(map(str, bad)))[:4]}")
    return not bad


async def main() -> int:
    parser = argparse.ArgumentParser(description="Yengil yuklama testi")
    parser.add_argument("--base", default="http://127.0.0.1", help="Manzil (default: http://127.0.0.1)")
    parser.add_argument("--host", default=None, help="Host sarlavhasi (masalan smart-kassa.uz)")
    parser.add_argument("--users", type=int, default=5, help="Parallel so'rovlar (default: 5)")
    parser.add_argument("--requests", type=int, default=10, help="Har endpointga so'rov soni (default: 10)")
    parser.add_argument("--user", default="miraziz")
    parser.add_argument("--password", default=None, help="Bo'sh qoldirilsa .env dan olinadi")
    args = parser.parse_args()

    import os
    password = args.password or os.getenv("PRIMARY_ADMIN_PASSWORD", "")
    if not password:
        print("XATO: parol berilmagan (--password yoki .env dagi PRIMARY_ADMIN_PASSWORD)")
        return 1

    headers = {"Host": args.host} if args.host else {}
    limits = httpx.Limits(max_connections=args.users, max_keepalive_connections=args.users)

    async with httpx.AsyncClient(base_url=args.base, headers=headers,
                                 timeout=30.0, limits=limits) as client:
        print(f"Manzil: {args.base}" + (f" (Host: {args.host})" if args.host else ""))
        print(f"Parallel: {args.users} | Har endpointga: {args.requests} ta so'rov")
        print()

        # --- 1. Sog'liq: autentifikatsiyasiz ---------------------------------
        ms, code = await timed(client, "GET", "/health")
        if not isinstance(code, int) or code >= 400:
            print(f"Ilova javob bermayapti: {code}")
            return 1
        print(f"Ilova tirik ({ms:.0f} ms). Kirilmoqda...")

        # --- 2. Kirish --------------------------------------------------------
        started = time.perf_counter()
        auth = await client.post("/auth/token", data={
            "username": args.user, "password": password, "force": "true"})
        login_ms = (time.perf_counter() - started) * 1000
        if auth.status_code != 200:
            print(f"XATO: kirib bo'lmadi ({auth.status_code}) {auth.text[:120]}")
            return 1
        token = auth.json()["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"
        print(f"Kirish muvaffaqiyatli ({login_ms:.0f} ms — parol hash'i sekin, bu normal)")
        print()

        # --- 3. O'qish endpointlari ------------------------------------------
        endpoints = [
            ("sog'liq", "GET", "/health"),
            ("sayt (SPA)", "GET", "/"),
            ("mahsulotlar", "GET", "/inventory/products?limit=100"),
            ("mijozlar", "GET", "/crm/clients"),
            ("savdolar", "GET", "/sales/?limit=50"),
            ("statistika", "GET", "/finance/stats"),
            ("smena", "GET", "/pos/shifts/active"),
        ]

        print("Natijalar:")
        all_ok = True
        for label, method, path in endpoints:
            semaphore = asyncio.Semaphore(args.users)

            async def one():
                async with semaphore:
                    return await timed(client, method, path)

            results = await asyncio.gather(*[one() for _ in range(args.requests)])
            samples = [ms for ms, _ in results]
            codes = [code for _, code in results]
            all_ok &= report(label, samples, codes)

        print()
        print("Izoh: p50 — odatiy javob, p95 — sekin uchdan biri.")
        print("Kassada 300 ms gacha sezilmaydi, 1000 ms dan yuqorisi bezovta qiladi.")
        return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
