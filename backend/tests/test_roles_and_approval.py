"""Rollar bo'yicha cheklovlar va menejer tasdig'ini himoyalash."""
import pytest

ADMIN = "miraziz"
ADMIN_PW = "test-admin-password-123"


@pytest.fixture(scope="module")
def warehouse(client, auth):
    import uuid

    username = f"ombor_{uuid.uuid4().hex[:6]}"
    password = "Ombor-Parol-123"
    r = client.post("/auth/employees", headers=auth, json={
        "username": username, "password": password, "role": "warehouse",
        "permissions": "", "full_name": "Omborchi",
    })
    assert r.status_code == 200, r.text
    token = client.post("/auth/token", data={
        "username": username, "password": password, "force": "true",
    })
    assert token.status_code == 200, token.text
    return {"Authorization": f"Bearer {token.json()['access_token']}"}


def test_warehouse_cannot_sell_or_touch_money(client, warehouse):
    """Omborchi faqat ombor va firmalar bilan ishlaydi.

    Ilgari u sotishi, smena ochishi, mijoz qarzini yopishi va xarajat
    kiritishi mumkin edi — bunda smenasi bo'lmagani uchun uning "to'lovi"
    hech qaysi kassa hisobida ko'rinmasdi.
    """
    sale = client.post("/sales/", headers=warehouse, json={
        "total_amount": 1000, "payment_method": "cash",
        "items": [{"product_id": 1, "quantity": 1, "price": 1000}],
        "cash_amount": 1000,
    })
    assert sale.status_code == 403, f"omborchi sotdi: {sale.status_code}"

    expense = client.post("/finance/expenses", headers=warehouse, json={
        "reason": "test", "category": "Boshqa", "amount": 100, "payment_method": "cash",
    })
    assert expense.status_code == 403, f"omborchi xarajat kiritdi: {expense.status_code}"

    payment = client.post("/finance/payments", headers=warehouse, json={
        "client_id": 1, "amount": 100, "payment_method": "cash",
    })
    assert payment.status_code == 403, f"omborchi to'lov yozdi: {payment.status_code}"


def test_warehouse_cannot_read_sales_or_clients(client, warehouse):
    """Savdolar va mijozlar ro'yxati omborchiga kerak emas (qarzlar ko'rinadi)."""
    assert client.get("/sales/", headers=warehouse).status_code == 403
    assert client.get("/crm/clients", headers=warehouse).status_code == 403


def test_warehouse_keeps_its_own_area(client, warehouse):
    """Cheklovlar omborchining O'Z ishini buzmasligi kerak."""
    assert client.get("/inventory/products", headers=warehouse).status_code == 200
    assert client.get("/suppliers/", headers=warehouse).status_code == 200


def test_manager_password_guessing_is_throttled_and_logged(client, auth):
    """Menejer parolini kassadan turib cheksiz taxmin qilib bo'lmasin.

    Muvaffaqiyatli topilgan parol /auth/token uchun ham yaraydi — ya'ni bu
    to'liq huquq eskalatsiyasi edi, hech qanday iz qoldirmasdan.
    """
    p = client.post("/inventory/products", headers=auth, json={
        "name": "Tasdiq testi", "barcode": "TEST-APPROVE-1", "buy_price": 10.0,
        "sell_price": 100.0, "stock": 50.0, "is_infinite": False,
        "unit": "dona", "category_id": None, "is_favorite": False,
    }).json()

    client.post("/pos/shifts/open", headers=auth, json={"opening_balance": 0})
    sale = client.post("/sales/", headers=auth, json={
        "total_amount": 100.0, "payment_method": "cash",
        "items": [{"product_id": p["id"], "quantity": 1, "price": 100.0}],
        "cash_amount": 100.0,
    })
    assert sale.status_code == 200, sale.text
    sale_id = sale.json()["id"]

    codes = []
    for i in range(8):
        r = client.post(f"/sales/{sale_id}/refund", headers=auth, json={
            "manager_username": ADMIN, "manager_password": f"noto-g-ri-{i}",
        })
        codes.append(r.status_code)

    assert 429 in codes, f"parol taxmin qilish cheklanmadi: {codes}"
    assert codes.index(429) <= 6, f"cheklov juda kech ishladi: {codes}"

    logs = client.get("/audit/logs", headers=auth, params={"action": "TASDIQ_XATO"}).json()
    assert logs, "muvaffaqiyatsiz tasdiq urinishi jurnalga yozilmadi"
