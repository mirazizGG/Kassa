"""Audit topgan xavfsizlik teshiklari qaytib kelmasligi uchun testlar."""


def test_products_and_categories_require_auth(client):
    """Ilgari bu ikki endpoint tokensiz ochiq edi va KELISH NARXINI ham berardi."""
    for path in ("/inventory/products", "/inventory/categories"):
        r = client.get(path)
        assert r.status_code == 401, f"{path} tokensiz ochiq qoldi: {r.status_code}"


def test_no_endpoint_is_unauthenticated(client):
    """Ochiq qolgan yangi endpoint qo'shilib ketmasin."""
    public = {"/health", "/favicon.ico", "/", "/openapi.json", "/docs", "/redoc",
              "/docs/oauth2-redirect", "/auth/token"}
    import main

    unguarded = []
    for route in main.app.routes:
        path = getattr(route, "path", "")
        if path in public or path.startswith("/uploads"):
            continue
        endpoint = getattr(route, "endpoint", None)
        if endpoint is None:
            continue
        params = getattr(endpoint, "__annotations__", {})
        if "current_user" not in params:
            unguarded.append(f"{sorted(getattr(route, 'methods', []) or [])} {path}")
    assert not unguarded, "Autentifikatsiyasiz endpointlar: " + ", ".join(unguarded)


def test_client_create_cannot_mint_balance(client, auth):
    """Eng og'ir teshik: kassir o'ziga balans/bonus 'chizib' olishi mumkin edi."""
    r = client.post(
        "/crm/clients",
        headers=auth,
        json={
            "name": "Balans hujumi",
            "phone": "+998901234567",
            "balance": 999_999_999,
            "bonus_balance": 999_999_999,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["balance"] == 0, f"balans chizib olindi: {body['balance']}"
    assert body["bonus_balance"] == 0, f"bonus chizib olindi: {body['bonus_balance']}"


def test_production_rejects_placeholder_secret_key():
    """.env.example dagi namunaviy kalit bilan production ishga tushmasligi kerak."""
    import importlib
    import os
    import core

    saved = dict(os.environ)
    try:
        for placeholder in sorted(core._PLACEHOLDER_SECRET_KEYS) + ["qisqa"]:
            os.environ["APP_ENV"] = "production"
            os.environ["SECRET_KEY"] = placeholder
            try:
                importlib.reload(core)
            except RuntimeError:
                pass  # kutilgan natija
            else:
                raise AssertionError(f"production zaif kalit bilan ishga tushdi: {placeholder!r}")
    finally:
        os.environ.clear()
        os.environ.update(saved)
        importlib.reload(core)


def test_product_with_sales_history_cannot_be_deleted(client, auth):
    """Sotilgan mahsulotni o'chirish tarixni buzardi va foydani sun'iy oshirardi."""
    p = client.post("/inventory/products", headers=auth, json={
        "name": "O'chmaydigan", "barcode": "TEST-DEL-1", "buy_price": 100.0,
        "sell_price": 200.0, "stock": 5.0, "is_infinite": False,
        "unit": "dona", "category_id": None, "is_favorite": False,
    }).json()

    client.post("/pos/shifts/open", headers=auth, json={"opening_balance": 0})
    sale = client.post("/sales/", headers=auth, json={
        "total_amount": 200.0, "payment_method": "cash",
        "items": [{"product_id": p["id"], "quantity": 1, "price": 200.0}],
        "cash_amount": 200.0, "card_amount": 0, "transfer_amount": 0,
        "debt_amount": 0, "bonus_spent": 0,
    })
    assert sale.status_code == 200, sale.text

    r = client.delete(f"/inventory/products/{p['id']}", headers=auth)
    assert r.status_code == 409, f"sotilgan mahsulot o'chirildi: {r.status_code}"

    still = client.get("/inventory/products", headers=auth).json()
    assert any(x["id"] == p["id"] for x in still), "mahsulot baribir yo'qoldi"


def test_client_with_history_cannot_be_deleted(client, auth):
    c = client.post("/crm/clients", headers=auth,
                    json={"name": "Tarixli mijoz", "phone": "+998901119999"}).json()
    r = client.post(f"/crm/clients/{c['id']}/pay", headers=auth,
                    json={"client_id": c["id"], "amount": 1000, "payment_method": "cash"})
    assert r.status_code == 200, r.text

    # Balansni nolga qaytaramiz, aks holda eski tekshiruv ishlab ketadi.
    client.post(f"/crm/clients/{c['id']}/pay", headers=auth,
                json={"client_id": c["id"], "amount": 1, "payment_method": "cash"})

    d = client.delete(f"/crm/clients/{c['id']}", headers=auth)
    assert d.status_code in (400, 409), f"to'lov tarixi bor mijoz o'chirildi: {d.status_code}"


def test_primary_admin_cannot_be_deleted(client, auth):
    me = client.get("/auth/employees", headers=auth).json()
    admin = next(e for e in me if e["username"] == "miraziz")
    r = client.delete(f"/auth/employees/{admin['id']}", headers=auth)
    assert r.status_code in (400, 403), r.text


def test_products_pagination_is_opt_in_and_reports_the_total(client, auth):
    """`limit` berilmasa - qirqish YO'Q.

    Sukut bo'yicha limit qo'yilsa, eski chaqiruvlar jimgina qirqilib qolardi:
    sahifa "hammasi shu" deb ko'rsatib turib, katalogning bir qismini
    yashirardi. Auditda aynan shunday xulq alohida kamchilik edi.
    """
    # Bir nechta mahsulot yaratamiz (avvalgi testlardan ham qolgan).
    for i in range(3):
        client.post("/inventory/products", headers=auth, json={
            "name": f"Sahifalash {i}", "barcode": f"TEST-PAGE-{i}",
            "buy_price": 10.0, "sell_price": 20.0, "stock": 1.0,
            "is_infinite": False, "unit": "dona", "category_id": None,
            "is_favorite": False,
        })

    full = client.get("/inventory/products", headers=auth)
    assert full.status_code == 200
    total = int(full.headers["X-Total-Count"])
    assert len(full.json()) == total, "limitsiz so'rov qirqildi"
    assert total >= 3

    page = client.get("/inventory/products", headers=auth, params={"limit": 2})
    assert page.status_code == 200
    assert len(page.json()) == 2
    assert int(page.headers["X-Total-Count"]) == total, (
        "sahifalanganda jami son o'zgarib ketdi"
    )

    second = client.get("/inventory/products", headers=auth,
                        params={"limit": 2, "offset": 2})
    assert second.status_code == 200
    first_ids = {p["id"] for p in page.json()}
    second_ids = {p["id"] for p in second.json()}
    assert not (first_ids & second_ids), "sahifalar bir-birini takrorlayapti"


def test_products_limit_is_clamped(client, auth):
    r = client.get("/inventory/products", headers=auth, params={"limit": 100000})
    assert r.status_code == 200
    assert len(r.json()) <= 500, "limit cheklanmadi"
