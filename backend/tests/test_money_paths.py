"""Pul harakati bo'yicha regressiya testlari.

Bu yo'llar tizimda eng qimmati: xato bo'lsa kassada pul yoki omborda tovar
yo'qoladi va buni hech kim darhol sezmaydi. Shu sababli ular birinchi bo'lib
testga olindi.
"""
import pytest

ADMIN = "miraziz"
ADMIN_PW = "test-admin-password-123"


def _product(client, auth, **over):
    body = {
        "name": over.pop("name", "Test mahsulot"),
        "barcode": over.pop("barcode", None),
        "buy_price": 1000.0,
        "sell_price": 1500.0,
        "stock": 10.0,
        "is_infinite": False,
        "unit": "dona",
        "category_id": None,
        "is_favorite": False,
    }
    body.update(over)
    r = client.post("/inventory/products", headers=auth, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _stock(client, auth, product_id):
    r = client.get("/inventory/products", headers=auth)
    assert r.status_code == 200, r.text
    return next(p["stock"] for p in r.json() if p["id"] == product_id)


def _sale(client, auth, product, qty=1, **over):
    total = product["sell_price"] * qty
    body = {
        "total_amount": total,
        "payment_method": "cash",
        "items": [{"product_id": product["id"], "quantity": qty, "price": product["sell_price"]}],
        "cash_amount": total,
        "card_amount": 0,
        "transfer_amount": 0,
        "debt_amount": 0,
        "bonus_spent": 0,
    }
    body.update(over)
    return client.post("/sales/", headers=auth, json=body)


@pytest.fixture(scope="module", autouse=True)
def open_shift(client, auth):
    client.post("/pos/shifts/open", headers=auth, json={"opening_balance": 0})
    yield


def test_sale_decrements_stock(client, auth):
    p = _product(client, auth, name="Qoldiq kamayadi", barcode="TEST-STOCK-1")
    r = _sale(client, auth, p, qty=3)
    assert r.status_code == 200, r.text
    assert _stock(client, auth, p["id"]) == 7.0


def test_sale_cannot_oversell(client, auth):
    p = _product(client, auth, name="Ortiqcha sotib bo'lmaydi", barcode="TEST-STOCK-2", stock=2.0)
    r = _sale(client, auth, p, qty=5)
    assert r.status_code in (400, 409), r.text
    assert _stock(client, auth, p["id"]) == 2.0, "muvaffaqiyatsiz sotuv qoldiqni o'zgartirdi"


def test_refund_restores_stock(client, auth):
    p = _product(client, auth, name="Vozvrat qoldiqni tiklaydi", barcode="TEST-STOCK-3")
    sale = _sale(client, auth, p, qty=4).json()
    assert _stock(client, auth, p["id"]) == 6.0

    r = client.post(
        f"/sales/{sale['id']}/refund",
        headers=auth,
        json={"manager_username": ADMIN, "manager_password": ADMIN_PW},
    )
    assert r.status_code == 200, r.text
    assert _stock(client, auth, p["id"]) == 10.0


def test_infinite_product_stock_never_moves(client, auth):
    """Audit topgan xato: cheksiz mahsulot sotuvda kamaymasdi, lekin vozvratda OSHARDI."""
    p = _product(client, auth, name="Cheksiz", barcode="TEST-INF-1", is_infinite=True, stock=5.0)

    sale = _sale(client, auth, p, qty=3).json()
    assert _stock(client, auth, p["id"]) == 5.0, "cheksiz mahsulot sotuvda kamaydi"

    r = client.post(
        f"/sales/{sale['id']}/refund",
        headers=auth,
        json={"manager_username": ADMIN, "manager_password": ADMIN_PW},
    )
    assert r.status_code == 200, r.text
    assert _stock(client, auth, p["id"]) == 5.0, "cheksiz mahsulot vozvratdan keyin oshib ketdi"


def test_refund_is_not_repeatable(client, auth):
    p = _product(client, auth, name="Ikki marta vozvrat", barcode="TEST-REF-2")
    sale = _sale(client, auth, p, qty=2).json()
    approval = {"manager_username": ADMIN, "manager_password": ADMIN_PW}

    assert client.post(f"/sales/{sale['id']}/refund", headers=auth, json=approval).status_code == 200
    second = client.post(f"/sales/{sale['id']}/refund", headers=auth, json=approval)
    assert second.status_code == 400, "bir savdoni ikki marta qaytarib bo'ldi"
    assert _stock(client, auth, p["id"]) == 10.0, "ikkinchi vozvrat qoldiqni yana oshirdi"


def test_refund_requires_manager_credentials(client, auth):
    p = _product(client, auth, name="Tasdiqsiz vozvrat", barcode="TEST-REF-3")
    sale = _sale(client, auth, p, qty=1).json()
    r = client.post(
        f"/sales/{sale['id']}/refund",
        headers=auth,
        json={"manager_username": ADMIN, "manager_password": "noto'g'ri-parol"},
    )
    assert r.status_code == 403, r.text
    assert _stock(client, auth, p["id"]) == 9.0, "rad etilgan vozvrat qoldiqni o'zgartirdi"


def test_debt_sale_moves_client_balance_and_reverses_on_refund(client, auth):
    c = client.post("/crm/clients", headers=auth, json={"name": "Qarzdor", "phone": "+998901110011"}).json()
    p = _product(client, auth, name="Nasiya tovar", barcode="TEST-DEBT-1")

    total = p["sell_price"] * 2
    sale = _sale(
        client, auth, p, qty=2,
        payment_method="debt", client_id=c["id"],
        cash_amount=0, debt_amount=total,
    )
    assert sale.status_code == 200, sale.text
    sale = sale.json()

    after = client.get(f"/crm/clients/{c['id']}", headers=auth).json()
    assert after["balance"] == pytest.approx(-total), "qarz mijoz balansiga yozilmadi"

    r = client.post(
        f"/sales/{sale['id']}/refund",
        headers=auth,
        json={"manager_username": ADMIN, "manager_password": ADMIN_PW},
    )
    assert r.status_code == 200, r.text
    back = client.get(f"/crm/clients/{c['id']}", headers=auth).json()
    assert back["balance"] == pytest.approx(0), "vozvrat qarzni qaytarmadi"


def test_debt_payment_reduces_debt(client, auth):
    c = client.post("/crm/clients", headers=auth, json={"name": "To'lovchi", "phone": "+998901110022"}).json()
    p = _product(client, auth, name="Nasiya tovar 2", barcode="TEST-DEBT-2")
    total = p["sell_price"]
    _sale(client, auth, p, qty=1, payment_method="debt", client_id=c["id"],
          cash_amount=0, debt_amount=total)

    r = client.post(f"/crm/clients/{c['id']}/pay", headers=auth,
                    json={"client_id": c["id"], "amount": total, "payment_method": "cash"})
    assert r.status_code == 200, r.text
    assert r.json()["new_balance"] == pytest.approx(0)


def test_bonus_cannot_be_overspent(client, auth):
    c = client.post("/crm/clients", headers=auth, json={"name": "Bonusxo'r", "phone": "+998901110033"}).json()
    p = _product(client, auth, name="Bonus tovar", barcode="TEST-BONUS-1")
    total = p["sell_price"]
    r = _sale(client, auth, p, qty=1, client_id=c["id"], cash_amount=0, bonus_spent=total)
    assert r.status_code == 400, "yo'q bonusni sarflab bo'ldi"
    assert _stock(client, auth, p["id"]) == 10.0, "rad etilgan sotuv qoldiqni kamaytirdi"


def test_payment_for_missing_client_is_rejected(client, auth):
    """Audit topgan xato: yo'q mijozga to'lov 'muvaffaqiyatli' yozilardi."""
    r = client.post("/finance/payments", headers=auth,
                    json={"client_id": 99999, "amount": 50000, "payment_method": "cash"})
    assert r.status_code == 404, r.text


def test_underpaid_sale_is_rejected(client, auth):
    """Audit topgan eng og'ir pul xatosi: yetmagan to'lov 'naqd olindi' deb yozilardi.

    100 000 lik chek 30 000 karta va 0 naqd bilan qabul qilinardi, qolgan
    70 000 esa kassaga "tushgan" deb hisoblanardi. Smena yopilishida kassir
    aynan shu summaga kamomadda qolardi.
    """
    p = _product(client, auth, name="Kam to'lov", barcode="TEST-UNDERPAY-1",
                 sell_price=100_000.0)
    r = _sale(client, auth, p, qty=1, cash_amount=0, card_amount=30_000.0)
    assert r.status_code == 400, f"kam to'langan chek qabul qilindi: {r.status_code}"
    assert _stock(client, auth, p["id"]) == 10.0, "rad etilgan sotuv qoldiqni kamaytirdi"


def test_card_only_sale_records_no_cash(client, auth):
    """To'liq karta to'lovi kassaga naqd qo'shmasligi kerak."""
    p = _product(client, auth, name="Faqat karta", barcode="TEST-CARD-1", sell_price=50_000.0)
    r = _sale(client, auth, p, qty=1, cash_amount=0, card_amount=50_000.0, payment_method="card")
    assert r.status_code == 200, r.text
    assert r.json()["cash_amount"] == 0, "kartali sotuv kassaga naqd yozdi"
    assert r.json()["card_amount"] == 50_000.0


def test_split_cash_and_card_records_only_the_cash_part(client, auth):
    """Aralash to'lovda kassaga faqat haqiqiy naqd qismi tushishi kerak."""
    p = _product(client, auth, name="Aralash", barcode="TEST-SPLIT-1", sell_price=100_000.0)
    r = _sale(client, auth, p, qty=1, cash_amount=70_000.0, card_amount=30_000.0)
    assert r.status_code == 200, r.text
    assert r.json()["cash_amount"] == 70_000.0
    assert r.json()["card_amount"] == 30_000.0


def test_cash_with_change_records_only_the_net(client, auth):
    """Xaridor ortiqcha bergan bo'lsa, kassaga faqat chek summasi yozilsin."""
    p = _product(client, auth, name="Qaytim", barcode="TEST-CHANGE-1", sell_price=45_000.0)
    r = _sale(client, auth, p, qty=1, cash_amount=50_000.0)
    assert r.status_code == 200, r.text
    assert r.json()["cash_amount"] == 45_000.0, "qaytim ham kassaga yozilib ketdi"


def test_debt_sale_without_a_client_is_rejected(client, auth):
    """Auditdagi yagona aniqlanmaydigan pul teshigi.

    `debt_amount > 0` va `client_id = null` bilan chek o'tib ketardi: tovar
    ombordan chiqadi, tushum hisobga olinadi, smena kassasi tiyinigacha
    to'g'ri keladi — va qarz HECH KIMDA paydo bo'lmaydi.
    """
    p = _product(client, auth, name="Egasiz nasiya", barcode="TEST-NOCLIENT-1")
    r = _sale(client, auth, p, qty=1, client_id=None,
              cash_amount=0, debt_amount=p["sell_price"])
    assert r.status_code == 400, f"mijozsiz nasiya qabul qilindi: {r.status_code}"
    assert _stock(client, auth, p["id"]) == 10.0, "rad etilgan sotuv qoldiqni kamaytirdi"


def test_bonus_sale_without_a_client_is_rejected(client, auth):
    """Bonus ham mijozsiz sarflanmasin: chek arzonlashar, balansdan yechilmasdi."""
    p = _product(client, auth, name="Egasiz bonus", barcode="TEST-NOCLIENT-2")
    r = _sale(client, auth, p, qty=1, client_id=None,
              cash_amount=0, bonus_spent=p["sell_price"])
    assert r.status_code == 400, f"mijozsiz bonus qabul qilindi: {r.status_code}"
    assert _stock(client, auth, p["id"]) == 10.0


def test_sale_with_an_unknown_client_is_a_clean_404(client, auth):
    """Noma'lum client_id jimgina o'tib ketmasin."""
    p = _product(client, auth, name="Noma'lum mijoz", barcode="TEST-NOCLIENT-3")
    r = _sale(client, auth, p, qty=1, client_id=999999,
              cash_amount=0, debt_amount=p["sell_price"])
    assert r.status_code == 404, f"noma'lum mijoz bilan chek o'tdi: {r.status_code}"
    assert _stock(client, auth, p["id"]) == 10.0


def test_normal_cash_sale_without_a_client_still_works(client, auth):
    """Oddiy naqd sotuvda mijoz shart emas — cheklov faqat nasiya/bonusga tegishli."""
    p = _product(client, auth, name="Oddiy naqd", barcode="TEST-NOCLIENT-4")
    r = _sale(client, auth, p, qty=2)
    assert r.status_code == 200, r.text
    assert _stock(client, auth, p["id"]) == 8.0


def test_sale_response_reports_stock_after_the_sale(client, auth):
    """Javobdagi qoldiq sotuvdan KEYINGI holat bo'lishi kerak.

    Atomik UPDATE dan keyin ORM ob'ekti eskirgan bo'lardi (expire_on_commit=False),
    shuning uchun javobda sotuvdan oldingi qoldiq ketardi.
    """
    p = _product(client, auth, name="Javobdagi qoldiq", barcode="TEST-FRESH-1")
    r = _sale(client, auth, p, qty=3)
    assert r.status_code == 200, r.text

    item = r.json()["items"][0]
    assert item["product"] is not None
    assert item["product"]["stock"] == 7.0, (
        f"javobda eskirgan qoldiq: {item['product']['stock']} (kutilgan 7)"
    )
    assert _stock(client, auth, p["id"]) == 7.0


def test_duplicate_barcode_is_a_clean_conflict(client, auth):
    """Takroriy shtrix-kod tushunarli xato bermoqda, 500 emas."""
    body = {
        "name": "Birinchi", "barcode": "TEST-DUP-BARCODE", "buy_price": 10.0,
        "sell_price": 20.0, "stock": 5.0, "is_infinite": False,
        "unit": "dona", "category_id": None, "is_favorite": False,
    }
    first = client.post("/inventory/products", headers=auth, json=body)
    assert first.status_code == 200, first.text

    second = client.post("/inventory/products", headers=auth,
                         json={**body, "name": "Ikkinchi"})
    assert second.status_code == 409, f"kutilgan 409, olingan {second.status_code}"
    assert "Birinchi" in second.json()["detail"], "xatoda qaysi tovar bandligi yozilmagan"


def test_product_with_zero_stock_is_allowed(client, auth):
    """Tugagan tovar katalogda qolishi kerak - qoldiq 0 to'g'ri qiymat."""
    r = client.post("/inventory/products", headers=auth, json={
        "name": "Tugagan tovar", "barcode": "TEST-ZERO-STOCK", "buy_price": 10.0,
        "sell_price": 20.0, "stock": 0.0, "is_infinite": False,
        "unit": "dona", "category_id": None, "is_favorite": False,
    })
    assert r.status_code == 200, r.text
    assert r.json()["stock"] == 0.0


def test_sales_list_reports_the_real_total(client, auth):
    """Ilgari sahifa oxirgi 100 tani olib, boshqa hech narsa ko'rsatmasdi.

    Ko'p chekli kunda ertalabki savdolar ekrandan yo'qolardi, ular bilan
    birga VOZVRAT tugmasi ham - u faqat shu ro'yxatda bor.
    """
    r = client.get("/sales/", headers=auth, params={"limit": 3})
    assert r.status_code == 200, r.text
    assert len(r.json()) <= 3

    total = r.headers.get("X-Total-Count")
    assert total is not None, "X-Total-Count sarlavhasi yo'q"
    assert int(total) >= len(r.json())

    if int(total) > 3:
        page2 = client.get("/sales/", headers=auth, params={"limit": 3, "skip": 3})
        assert page2.status_code == 200
        first_ids = {s["id"] for s in r.json()}
        second_ids = {s["id"] for s in page2.json()}
        assert not (first_ids & second_ids), "sahifalar takrorlanyapti"


def test_sales_list_limit_is_clamped(client, auth):
    r = client.get("/sales/", headers=auth, params={"limit": 100000})
    assert r.status_code == 200
    assert len(r.json()) <= 500
