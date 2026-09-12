"""Takroriy chek va son maydonlarining validatsiyasi."""


def _product(client, auth, barcode, **over):
    body = {
        "name": f"Tovar {barcode}", "barcode": barcode, "buy_price": 100.0,
        "sell_price": 1000.0, "stock": 20.0, "is_infinite": False,
        "unit": "dona", "category_id": None, "is_favorite": False,
    }
    body.update(over)
    r = client.post("/inventory/products", headers=auth, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _stock(client, auth, pid):
    return next(p["stock"] for p in client.get("/inventory/products", headers=auth).json()
                if p["id"] == pid)


def _payload(product, qty=1, **over):
    total = product["sell_price"] * qty
    body = {
        "total_amount": total, "payment_method": "cash",
        "items": [{"product_id": product["id"], "quantity": qty, "price": product["sell_price"]}],
        "cash_amount": total, "card_amount": 0, "transfer_amount": 0,
        "debt_amount": 0, "bonus_spent": 0,
    }
    body.update(over)
    return body


def test_same_idempotency_key_creates_one_sale(client, auth):
    """Ikki marta bosilgan 'To'lash' ikkita chek yozmasligi kerak."""
    client.post("/pos/shifts/open", headers=auth, json={"opening_balance": 0})
    p = _product(client, auth, "TEST-IDEM-1")
    body = _payload(p, qty=3, idempotency_key="tugma-ikki-marta-bosildi")

    first = client.post("/sales/", headers=auth, json=body)
    assert first.status_code == 200, first.text
    after_first = _stock(client, auth, p["id"])
    assert after_first == 17.0

    second = client.post("/sales/", headers=auth, json=body)
    assert second.status_code == 200, second.text

    assert second.json()["id"] == first.json()["id"], "ikkinchi so'rov yangi chek yaratdi"
    assert _stock(client, auth, p["id"]) == 17.0, "qoldiq ikki marta kamaydi"


def test_different_keys_create_different_sales(client, auth):
    client.post("/pos/shifts/open", headers=auth, json={"opening_balance": 0})
    p = _product(client, auth, "TEST-IDEM-2")

    a = client.post("/sales/", headers=auth, json=_payload(p, idempotency_key="chek-a"))
    b = client.post("/sales/", headers=auth, json=_payload(p, idempotency_key="chek-b"))
    assert a.status_code == 200 and b.status_code == 200
    assert a.json()["id"] != b.json()["id"], "har xil kalitli cheklar birlashib ketdi"
    assert _stock(client, auth, p["id"]) == 18.0


def test_sale_without_a_key_still_works(client, auth):
    """Kalitsiz eski mijozlar ham ishlashda davom etsin."""
    client.post("/pos/shifts/open", headers=auth, json={"opening_balance": 0})
    p = _product(client, auth, "TEST-IDEM-3")
    r = client.post("/sales/", headers=auth, json=_payload(p))
    assert r.status_code == 200, r.text
    r2 = client.post("/sales/", headers=auth, json=_payload(p))
    assert r2.status_code == 200 and r2.json()["id"] != r.json()["id"]


def test_nan_and_infinity_are_rejected(client, auth):
    """NaN REAL ustunni NULL ga aylantirib, ro'yxat endpointlarini 500 qilardi."""
    client.post("/pos/shifts/open", headers=auth, json={"opening_balance": 0})
    p = _product(client, auth, "TEST-NAN-1")

    # NaN/Infinity JSON standartida yo'q, shuning uchun xom tanani yuboramiz.
    for bad in ("NaN", "Infinity", "-Infinity"):
        raw = (
            '{"total_amount": %s, "payment_method": "cash", '
            '"items": [{"product_id": %d, "quantity": 1, "price": 1000}], '
            '"cash_amount": 1000}' % (bad, p["id"])
        )
        r = client.post(
            "/sales/",
            headers={**auth, "Content-Type": "application/json"},
            content=raw,
        )
        assert r.status_code == 422, f"{bad} qabul qilindi: {r.status_code}"

    assert _stock(client, auth, p["id"]) == 20.0


def test_negative_and_zero_quantities_are_rejected(client, auth):
    client.post("/pos/shifts/open", headers=auth, json={"opening_balance": 0})
    p = _product(client, auth, "TEST-NEG-1")

    for qty in (-5, 0):
        r = client.post("/sales/", headers=auth, json=_payload(p, qty=1) | {
            "items": [{"product_id": p["id"], "quantity": qty, "price": 1000.0}],
        })
        assert r.status_code == 422, f"quantity={qty} qabul qilindi"

    r = client.post("/sales/", headers=auth, json=_payload(p) | {"cash_amount": -100})
    assert r.status_code == 422, "manfiy naqd qabul qilindi"

    assert _stock(client, auth, p["id"]) == 20.0


def test_empty_cart_is_rejected(client, auth):
    client.post("/pos/shifts/open", headers=auth, json={"opening_balance": 0})
    r = client.post("/sales/", headers=auth, json={
        "total_amount": 1000, "payment_method": "cash", "items": [], "cash_amount": 1000,
    })
    assert r.status_code == 422, "bo'sh savat qabul qilindi"


def test_product_edit_refuses_a_stale_stock(client, auth):
    """Forma ochiq turganda sotilgan tovar qoldig'i qayta tiklanmasin."""
    client.post("/pos/shifts/open", headers=auth, json={"opening_balance": 0})
    p = _product(client, auth, "TEST-STALE-1")

    # Menejer formani ochdi: qoldiq 20.
    seen_stock = p["stock"]

    # Shu payt 4 dona sotildi.
    client.post("/sales/", headers=auth, json=_payload(p, qty=4))
    assert _stock(client, auth, p["id"]) == 16.0

    # Menejer eski qiymat bilan saqlaydi.
    stale = client.put(f"/inventory/products/{p['id']}", headers=auth, json={
        "name": p["name"], "barcode": p["barcode"], "buy_price": 100.0,
        "sell_price": 1200.0, "stock": seen_stock, "is_infinite": False,
        "unit": "dona", "category_id": None, "is_favorite": False,
        "expected_stock": seen_stock,
    })
    assert stale.status_code == 409, f"eski qoldiq qayta yozildi: {stale.status_code}"
    assert _stock(client, auth, p["id"]) == 16.0, "sotilgan tovar omborga qaytdi"

    # Yangilangan qiymat bilan saqlash ishlashi kerak.
    ok = client.put(f"/inventory/products/{p['id']}", headers=auth, json={
        "name": p["name"], "barcode": p["barcode"], "buy_price": 100.0,
        "sell_price": 1200.0, "stock": 16.0, "is_infinite": False,
        "unit": "dona", "category_id": None, "is_favorite": False,
        "expected_stock": 16.0,
    })
    assert ok.status_code == 200, ok.text
    assert ok.json()["sell_price"] == 1200.0
