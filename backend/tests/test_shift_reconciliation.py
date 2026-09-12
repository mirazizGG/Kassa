"""Smena kassasini hisoblash — do'kon uchun eng og'riqli joy.

Audit uchta muammo topgan edi:
  1) xarajatlar hisobga umuman kirmasdi, shuning uchun kassadan pul olingan
     har kuni "kamomad" chiqardi va tushuntirish xati odatiy holga aylanardi;
  2) yopilgan smena hisobi har so'rovda QAYTA hisoblanardi, shuning uchun
     keyinroq qilingan vozvrat kassir imzolagan raqamni o'zgartirib yuborardi;
  3) smenani faqat egasi yopa olardi — kassir ketib qolsa, smena abadiy ochiq.
"""
ADMIN = "miraziz"
ADMIN_PW = "test-admin-password-123"


def _fresh_shift(client, auth, opening=0):
    client.post("/pos/shifts/close", headers=auth,
                json={"closing_balance": 0, "note": "test reset"})
    r = client.post("/pos/shifts/open", headers=auth, json={"opening_balance": opening})
    assert r.status_code == 200, r.text
    return r.json()


def _product(client, auth, barcode, price=1000.0):
    return client.post("/inventory/products", headers=auth, json={
        "name": f"Tovar {barcode}", "barcode": barcode, "buy_price": 100.0,
        "sell_price": price, "stock": 100.0, "is_infinite": False,
        "unit": "dona", "category_id": None, "is_favorite": False,
    }).json()


def _cash_sale(client, auth, product, qty=1):
    total = product["sell_price"] * qty
    r = client.post("/sales/", headers=auth, json={
        "total_amount": total, "payment_method": "cash",
        "items": [{"product_id": product["id"], "quantity": qty, "price": product["sell_price"]}],
        "cash_amount": total, "card_amount": 0, "transfer_amount": 0,
        "debt_amount": 0, "bonus_spent": 0,
    })
    assert r.status_code == 200, r.text
    return r.json()


def test_cash_expense_is_subtracted_from_expected_cash(client, auth):
    _fresh_shift(client, auth, opening=10_000)
    p = _product(client, auth, "TEST-EXP-1", price=5_000.0)
    _cash_sale(client, auth, p)

    before = client.get("/pos/shifts/active", headers=auth).json()
    assert before["expected_cash"] == 15_000, before

    r = client.post("/finance/expenses", headers=auth, json={
        "reason": "Kassadan olindi", "category": "Boshqa",
        "amount": 4_000, "payment_method": "cash",
    })
    assert r.status_code == 200, r.text

    after = client.get("/pos/shifts/active", headers=auth).json()
    assert after["total_expenses"] == 4_000, after
    assert after["expected_cash"] == 11_000, (
        f"naqd xarajat kassadan ayirilmadi: {after['expected_cash']} (kutilgan 11 000)"
    )


def test_non_cash_expense_does_not_touch_the_till(client, auth):
    _fresh_shift(client, auth, opening=10_000)

    r = client.post("/finance/expenses", headers=auth, json={
        "reason": "Bank orqali", "category": "Boshqa",
        "amount": 7_000, "payment_method": "transfer",
    })
    assert r.status_code == 200, r.text

    shift = client.get("/pos/shifts/active", headers=auth).json()
    assert shift["total_expenses"] == 0, "naqd bo'lmagan xarajat kassadan ayirildi"
    assert shift["expected_cash"] == 10_000


def test_closed_shift_reconciliation_is_frozen(client, auth):
    """Yopilgandan keyin qilingan vozvrat o'tgan smena hisobini o'zgartirmasin."""
    _fresh_shift(client, auth, opening=0)
    p = _product(client, auth, "TEST-FROZEN-1", price=20_000.0)
    sale = _cash_sale(client, auth, p)

    closed = client.post("/pos/shifts/close", headers=auth,
                         json={"closing_balance": 20_000, "note": ""})
    assert closed.status_code == 200, closed.text
    body = closed.json()
    assert body["expected_cash"] == 20_000
    assert body["cash_difference"] == 0

    shift_id = body["id"]

    # Yopilgandan KEYIN vozvrat qilamiz.
    r = client.post(f"/sales/{sale['id']}/refund", headers=auth,
                    json={"manager_username": ADMIN, "manager_password": ADMIN_PW})
    assert r.status_code == 200, r.text

    history = client.get("/pos/shifts/history", headers=auth).json()
    frozen = next(s for s in history if s["id"] == shift_id)
    assert frozen["expected_cash"] == 20_000, (
        f"yopilgan smena hisobi vozvratdan keyin o'zgardi: {frozen['expected_cash']}"
    )
    assert frozen["cash_difference"] == 0


def test_shift_close_requires_a_note_only_when_short(client, auth):
    _fresh_shift(client, auth, opening=5_000)
    bad = client.post("/pos/shifts/close", headers=auth,
                      json={"closing_balance": 3_000, "note": ""})
    assert bad.status_code == 400, "farq bor, lekin sabab so'ralmadi"

    ok = client.post("/pos/shifts/close", headers=auth,
                     json={"closing_balance": 3_000, "note": "Kamomad sababi"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["cash_difference"] == -2_000


def test_admin_can_force_close_a_stranded_shift(client, auth):
    shift = _fresh_shift(client, auth, opening=1_000)

    no_note = client.post(f"/pos/shifts/{shift['id']}/force-close", headers=auth,
                          json={"closing_balance": 1_000, "note": ""})
    assert no_note.status_code == 400, "sababsiz majburiy yopish o'tdi"

    r = client.post(f"/pos/shifts/{shift['id']}/force-close", headers=auth,
                    json={"closing_balance": 1_000, "note": "Kassir ishga chiqmadi"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "closed"
    assert r.json()["closed_by"] is not None

    again = client.post(f"/pos/shifts/{shift['id']}/force-close", headers=auth,
                        json={"closing_balance": 1_000, "note": "yana"})
    assert again.status_code == 400, "yopilgan smena ikkinchi marta yopildi"


def test_cash_debt_payment_requires_an_open_shift(client, auth):
    """Naqd pul kassaga tushadi — uni kutadigan smena bo'lishi shart.

    Ilgari smena bo'lmasa shift_id NULL bo'lib qolardi va pul hech qaysi
    hisobga kirmasdi: yopilishda tushunarsiz ORTIQCHA chiqib, kassirdan
    tushuntirish talab qilinardi.
    """
    c = client.post("/crm/clients", headers=auth,
                    json={"name": "Smenasiz to'lov", "phone": "+998901239999"}).json()

    # Barcha smenalarni yopamiz.
    client.post("/pos/shifts/close", headers=auth,
                json={"closing_balance": 0, "note": "test reset"})

    blocked = client.post(f"/crm/clients/{c['id']}/pay", headers=auth,
                          json={"client_id": c["id"], "amount": 10_000,
                                "payment_method": "cash"})
    assert blocked.status_code == 409, (
        f"smenasiz naqd to'lov qabul qilindi: {blocked.status_code}"
    )

    # Naqd bo'lmagan to'lov smenasiz ham o'tishi kerak — u kassaga tegmaydi.
    transfer = client.post(f"/crm/clients/{c['id']}/pay", headers=auth,
                           json={"client_id": c["id"], "amount": 10_000,
                                 "payment_method": "transfer"})
    assert transfer.status_code == 200, transfer.text

    # Smena ochilgach naqd ham o'tadi.
    client.post("/pos/shifts/open", headers=auth, json={"opening_balance": 0})
    ok = client.post(f"/crm/clients/{c['id']}/pay", headers=auth,
                     json={"client_id": c["id"], "amount": 5_000,
                           "payment_method": "cash"})
    assert ok.status_code == 200, ok.text

    shift = client.get("/pos/shifts/active", headers=auth).json()
    assert shift["expected_cash"] == 5_000, (
        f"naqd to'lov smena kassasiga kirmadi: {shift['expected_cash']}"
    )


def test_finance_payments_endpoint_has_the_same_shift_rule(client, auth):
    c = client.post("/crm/clients", headers=auth,
                    json={"name": "Finance smena", "phone": "+998901238888"}).json()
    client.post("/pos/shifts/close", headers=auth,
                json={"closing_balance": 0, "note": "test reset"})

    r = client.post("/finance/payments", headers=auth,
                    json={"client_id": c["id"], "amount": 7_000, "payment_method": "cash"})
    assert r.status_code == 409, f"/finance/payments smenasiz naqdni qabul qildi: {r.status_code}"


def test_refund_of_an_earlier_shift_leaves_todays_drawer(client, auth):
    """Kechagi naqd sotuvni bugun qaytarsak, pul BUGUNGI kassadan chiqadi.

    Ilgari vozvrat na smenani, na vaqtni yozmasdi, va compute_shift_totals
    faqat o'z oynasidagi sotuvlarni sanardi — natijada kassir aynan shu
    summaga kamomadda qolib, tizim o'zi bilgan pul uchun tushuntirish xati
    yozardi.
    """
    # --- 1-smena: naqd sotuv va yopilish -----------------------------------
    _fresh_shift(client, auth, opening=0)
    p = _product(client, auth, "TEST-REFUND-SHIFT", price=20_000.0)
    sale = _cash_sale(client, auth, p)

    first = client.post("/pos/shifts/close", headers=auth,
                        json={"closing_balance": 20_000, "note": ""})
    assert first.status_code == 200, first.text
    first_id = first.json()["id"]
    assert first.json()["expected_cash"] == 20_000

    # --- 2-smena: o'sha chekni qaytaramiz ----------------------------------
    opened = client.post("/pos/shifts/open", headers=auth, json={"opening_balance": 0})
    assert opened.status_code == 200, opened.text

    r = client.post(f"/sales/{sale['id']}/refund", headers=auth,
                    json={"manager_username": ADMIN, "manager_password": ADMIN_PW})
    assert r.status_code == 200, r.text

    current = client.get("/pos/shifts/active", headers=auth).json()
    assert current["total_refunds"] == 20_000, (
        f"vozvrat smenaga yozilmadi: {current['total_refunds']}"
    )
    assert current["expected_cash"] == -20_000, (
        f"kassadan chiqqan pul hisobga olinmadi: {current['expected_cash']}"
    )

    # --- 1-smena hisobi muzlab qolgan bo'lishi kerak ------------------------
    history = client.get("/pos/shifts/history", headers=auth).json()
    frozen = next(s for s in history if s["id"] == first_id)
    assert frozen["expected_cash"] == 20_000, "yopilgan smena hisobi o'zgardi"


def test_same_shift_refund_is_not_counted_twice(client, auth):
    """Sotuv ham, vozvrat ham bitta smenada bo'lsa — bir marta hisoblansin.

    Bunday sotuv `status = "refunded"` bo'lgani uchun "completed" yig'indisidan
    allaqachon chiqib ketadi. Yana bir marta ayirsak, kassa ikki barobar kam
    ko'rinardi.
    """
    _fresh_shift(client, auth, opening=1_000)
    p = _product(client, auth, "TEST-REFUND-SAME", price=5_000.0)
    sale = _cash_sale(client, auth, p)

    before = client.get("/pos/shifts/active", headers=auth).json()
    assert before["expected_cash"] == 6_000

    r = client.post(f"/sales/{sale['id']}/refund", headers=auth,
                    json={"manager_username": ADMIN, "manager_password": ADMIN_PW})
    assert r.status_code == 200, r.text

    after = client.get("/pos/shifts/active", headers=auth).json()
    assert after["total_refunds"] == 0, (
        f"o'z smenasidagi vozvrat ikkinchi marta ayirildi: {after['total_refunds']}"
    )
    assert after["expected_cash"] == 1_000, (
        f"kassa ikki barobar kamaydi: {after['expected_cash']} (kutilgan 1 000)"
    )


def test_card_refund_does_not_touch_the_drawer(client, auth):
    """Kartadagi sotuvning vozvrati naqd kassaga tegmasligi kerak."""
    _fresh_shift(client, auth, opening=0)
    p = _product(client, auth, "TEST-REFUND-CARD", price=9_000.0)
    card_sale = client.post("/sales/", headers=auth, json={
        "total_amount": 9_000.0, "payment_method": "card",
        "items": [{"product_id": p["id"], "quantity": 1, "price": 9_000.0}],
        "cash_amount": 0, "card_amount": 9_000.0, "transfer_amount": 0,
        "debt_amount": 0, "bonus_spent": 0,
    })
    assert card_sale.status_code == 200, card_sale.text

    client.post("/pos/shifts/close", headers=auth, json={"closing_balance": 0, "note": ""})
    client.post("/pos/shifts/open", headers=auth, json={"opening_balance": 0})

    r = client.post(f"/sales/{card_sale.json()['id']}/refund", headers=auth,
                    json={"manager_username": ADMIN, "manager_password": ADMIN_PW})
    assert r.status_code == 200, r.text

    shift = client.get("/pos/shifts/active", headers=auth).json()
    assert shift["total_refunds"] == 0, "kartali vozvrat naqd kassadan ayirildi"
    assert shift["expected_cash"] == 0
