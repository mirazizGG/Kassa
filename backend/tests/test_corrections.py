"""Xato yozilgan yozuvlarni tuzatish yo'llari.

Audit topgan muammo: xarajat, qarz to'lovi va kirim bir marta yozilgach,
ularni na tuzatish, na o'chirish mumkin edi. Bitta xato raqam o'sha davrning
barcha hisobotlarini abadiy buzardi.
"""
ADMIN = "miraziz"
ADMIN_PW = "test-admin-password-123"


def test_expense_can_be_corrected(client, auth):
    made = client.post("/finance/expenses", headers=auth, json={
        "reason": "Noto'g'ri summa", "category": "Boshqa",
        "amount": 900_000, "payment_method": "cash",
    })
    assert made.status_code == 200, made.text
    expense_id = made.json()["id"]

    # Sababsiz tuzatish o'tmasligi kerak.
    no_reason = client.patch(f"/finance/expenses/{expense_id}", headers=auth,
                             json={"amount": 90_000})
    assert no_reason.status_code == 422

    fixed = client.patch(f"/finance/expenses/{expense_id}",
                         headers=auth, params={"reason": "Nol ortiqcha yozilgan"},
                         json={"amount": 90_000})
    assert fixed.status_code == 200, fixed.text
    assert fixed.json()["amount"] == 90_000


def test_expense_can_be_deleted_with_a_reason(client, auth):
    made = client.post("/finance/expenses", headers=auth, json={
        "reason": "Ortiqcha yozuv", "category": "Boshqa",
        "amount": 12_345, "payment_method": "cash",
    }).json()

    gone = client.delete(f"/finance/expenses/{made['id']}",
                         headers=auth, params={"reason": "Ikki marta kiritilgan"})
    assert gone.status_code == 200, gone.text

    remaining = client.get("/finance/expenses", headers=auth).json()
    assert not any(e["id"] == made["id"] for e in remaining), "xarajat o'chmadi"


def test_deleting_an_expense_returns_cash_to_the_till(client, auth):
    """Naqd xarajat bekor qilinsa, smena kassasi tiklanishi kerak."""
    client.post("/pos/shifts/close", headers=auth,
                json={"closing_balance": 0, "note": "reset"})
    client.post("/pos/shifts/open", headers=auth, json={"opening_balance": 30_000})

    made = client.post("/finance/expenses", headers=auth, json={
        "reason": "Kassadan", "category": "Boshqa",
        "amount": 8_000, "payment_method": "cash",
    }).json()

    with_expense = client.get("/pos/shifts/active", headers=auth).json()
    assert with_expense["expected_cash"] == 22_000

    client.delete(f"/finance/expenses/{made['id']}", headers=auth,
                  params={"reason": "Xato yozuv"})

    after = client.get("/pos/shifts/active", headers=auth).json()
    assert after["expected_cash"] == 30_000, (
        f"xarajat bekor qilingandan keyin kassa tiklanmadi: {after['expected_cash']}"
    )


def test_debt_payment_can_be_voided_and_balance_returns(client, auth):
    c = client.post("/crm/clients", headers=auth,
                    json={"name": "Bekor qilinadigan", "phone": "+998901230001"}).json()

    paid = client.post(f"/crm/clients/{c['id']}/pay", headers=auth,
                       json={"client_id": c["id"], "amount": 75_000, "payment_method": "cash"})
    assert paid.status_code == 200, paid.text
    assert paid.json()["new_balance"] == 75_000

    payments = client.get(f"/crm/clients/{c['id']}/history", headers=auth).json()
    payment_id = payments["payments"][0]["id"] if isinstance(payments, dict) else None
    if payment_id is None:
        import sqlalchemy  # fallback: oxirgi to'lovni topamiz
        payment_id = paid.json().get("payment_id")
    assert payment_id, "to'lov IDsi topilmadi"

    void = client.delete(f"/crm/payments/{payment_id}", headers=auth,
                         params={"reason": "Boshqa mijozga yozilgan"})
    assert void.status_code == 200, void.text
    assert void.json()["new_balance"] == 0, "balans qaytarilmadi"


def test_supply_can_be_voided_and_restores_price(client, auth):
    p = client.post("/inventory/products", headers=auth, json={
        "name": "Kirim tuzatish", "barcode": "TEST-SUPPLY-VOID", "buy_price": 500.0,
        "sell_price": 1000.0, "stock": 0.0, "is_infinite": False,
        "unit": "dona", "category_id": None, "is_favorite": False,
    }).json()

    first = client.post("/inventory/supplies", headers=auth, json={
        "product_id": p["id"], "quantity": 10, "buy_price": 600.0,
    })
    assert first.status_code == 200, first.text

    # Ikkinchi kirim xato tannarx bilan.
    bad = client.post("/inventory/supplies", headers=auth, json={
        "product_id": p["id"], "quantity": 5, "buy_price": 60_000.0,
    })
    assert bad.status_code == 200, bad.text

    current = next(x for x in client.get("/inventory/products", headers=auth).json()
                   if x["id"] == p["id"])
    assert current["buy_price"] == 60_000.0
    assert current["stock"] == 15.0

    undo = client.delete(f"/inventory/supplies/{bad.json()['id']}", headers=auth,
                         params={"reason": "Tannarxda nol ortiqcha"})
    assert undo.status_code == 200, undo.text

    fixed = next(x for x in client.get("/inventory/products", headers=auth).json()
                 if x["id"] == p["id"])
    assert fixed["stock"] == 10.0, f"qoldiq qaytarilmadi: {fixed['stock']}"
    assert fixed["buy_price"] == 600.0, f"tannarx tiklanmadi: {fixed['buy_price']}"


def test_audit_log_reports_the_real_total(client, auth):
    """Ilgari frontend faqat 100 ta yozuvni olib, shuni 'hammasi' deb ko'rsatardi."""
    r = client.get("/audit/logs", headers=auth, params={"limit": 5})
    assert r.status_code == 200, r.text
    assert len(r.json()) <= 5

    total = r.headers.get("X-Total-Count")
    assert total is not None, "X-Total-Count sarlavhasi yo'q"
    assert int(total) >= len(r.json())
    # Bu paytga qadar testlar ko'p amal qilgan — jami 5 tadan ko'p bo'lishi shart.
    assert int(total) > 5, f"jami son noto'g'ri: {total}"
