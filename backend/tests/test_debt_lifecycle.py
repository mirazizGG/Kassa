"""Qarz muddatining hayot sikli.

Bot do'konda aynan shu narsa uchun turibdi - qarz eslatmalari. Ammo eslatma
tayanadigan maydonni hech bir pul yo'li to'ldirmasdi: sotuv uni qo'ymasdi,
to'lov tozalamasdi, va hisoblash muddat KUNIda ham "o'tgan" deb chiqarardi.
"""
from datetime import timedelta

from utils.timezone import days_until, shop_date, shop_today, utc_now

ADMIN = "miraziz"
ADMIN_PW = "test-admin-password-123"


def _product(client, auth, barcode, price=10_000.0):
    return client.post("/inventory/products", headers=auth, json={
        "name": f"Qarz {barcode}", "barcode": barcode, "buy_price": 1000.0,
        "sell_price": price, "stock": 100.0, "is_infinite": False,
        "unit": "dona", "category_id": None, "is_favorite": False,
    }).json()


def test_countdown_uses_calendar_days_not_timedelta():
    """Muddat KUNIning o'zida natija 0 bo'lishi kerak, -1 emas.

    Ilgari `(due - now).days` ishlatilardi: manfiy timedelta pastga
    yaxlitlangani uchun ertalab soat 9 da ham -1 chiqib, mijozga
    "muddati o'tgan" deb yozilardi.
    """
    midnight_today = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
    assert days_until(midnight_today) == 0, "muddat kunida 'o'tgan' deb hisoblandi"
    assert days_until(utc_now() + timedelta(days=3)) == 3
    assert days_until(utc_now() - timedelta(days=1)) == -1


def test_debt_sale_sets_the_due_date(client, auth):
    """Nasiya sotuv muddatni O'ZI qo'yishi kerak."""
    c = client.post("/crm/clients", headers=auth,
                    json={"name": "Muddat mijozi", "phone": "+998901114444"}).json()
    assert c["debt_due_date"] is None

    settings = client.get("/settings", headers=auth).json()
    reminder_days = settings["debt_reminder_days"]

    p = _product(client, auth, "TEST-DUE-1")
    client.post("/pos/shifts/open", headers=auth, json={"opening_balance": 0})
    r = client.post("/sales/", headers=auth, json={
        "total_amount": p["sell_price"], "payment_method": "debt",
        "items": [{"product_id": p["id"], "quantity": 1, "price": p["sell_price"]}],
        "cash_amount": 0, "card_amount": 0, "transfer_amount": 0,
        "debt_amount": p["sell_price"], "bonus_spent": 0,
        "client_id": c["id"],
    })
    assert r.status_code == 200, r.text

    after = client.get(f"/crm/clients/{c['id']}", headers=auth).json()
    assert after["debt_due_date"] is not None, "nasiya sotuv muddat qo'ymadi"

    from datetime import datetime
    due = datetime.fromisoformat(after["debt_due_date"].replace("Z", ""))
    assert days_until(due) == max(reminder_days, 1), (
        f"muddat noto'g'ri: {days_until(due)} kun (kutilgan {reminder_days})"
    )


def test_paying_the_debt_clears_the_due_date(client, auth):
    """Qarz yopilgach, bot endi eslatma yubormasligi kerak."""
    c = client.post("/crm/clients", headers=auth,
                    json={"name": "To'lab bitirdi", "phone": "+998901115555"}).json()
    p = _product(client, auth, "TEST-DUE-2")

    client.post("/pos/shifts/open", headers=auth, json={"opening_balance": 0})
    client.post("/sales/", headers=auth, json={
        "total_amount": p["sell_price"], "payment_method": "debt",
        "items": [{"product_id": p["id"], "quantity": 1, "price": p["sell_price"]}],
        "cash_amount": 0, "debt_amount": p["sell_price"], "client_id": c["id"],
    })
    mid = client.get(f"/crm/clients/{c['id']}", headers=auth).json()
    assert mid["debt_due_date"] is not None
    assert mid["balance"] < 0

    paid = client.post(f"/crm/clients/{c['id']}/pay", headers=auth, json={
        "client_id": c["id"], "amount": p["sell_price"], "payment_method": "cash",
    })
    assert paid.status_code == 200, paid.text

    after = client.get(f"/crm/clients/{c['id']}", headers=auth).json()
    assert after["balance"] == 0
    assert after["debt_due_date"] is None, (
        "qarz yopilgan, lekin muddat qoldi - bot eslatma yuborishda davom etadi"
    )


def test_partial_payment_keeps_the_due_date(client, auth):
    """Qisman to'lovda muddat SAQLANISHI kerak - qarz hali bor."""
    c = client.post("/crm/clients", headers=auth,
                    json={"name": "Qisman to'lov", "phone": "+998901116666"}).json()
    p = _product(client, auth, "TEST-DUE-3", price=20_000.0)

    client.post("/pos/shifts/open", headers=auth, json={"opening_balance": 0})
    client.post("/sales/", headers=auth, json={
        "total_amount": 20_000.0, "payment_method": "debt",
        "items": [{"product_id": p["id"], "quantity": 1, "price": 20_000.0}],
        "cash_amount": 0, "debt_amount": 20_000.0, "client_id": c["id"],
    })

    client.post(f"/crm/clients/{c['id']}/pay", headers=auth, json={
        "client_id": c["id"], "amount": 5_000.0, "payment_method": "cash",
    })

    after = client.get(f"/crm/clients/{c['id']}", headers=auth).json()
    assert after["balance"] == -15_000.0
    assert after["debt_due_date"] is not None, "qarz qolgan, lekin muddat o'chirildi"
