"""Sessiya bekor qilish va fayl yuklash cheklovlari."""
import io

import pytest


@pytest.fixture(scope="module")
def confirmer(client, auth):
    """Firma amallarini tasdiqlovchi ALOHIDA menejer.

    O'z amalini o'zi tasdiqlab bo'lmaydi (ikki kishilik nazorat), shuning
    uchun testlarda ham alohida odam kerak.
    """
    import uuid

    username = f"tasdiqlovchi_{uuid.uuid4().hex[:8]}"
    password = "Tasdiq-Parol-123"
    r = client.post("/auth/employees", headers=auth, json={
        "username": username, "password": password, "role": "manager",
        "permissions": "", "full_name": "Tasdiqlovchi menejer",
    })
    assert r.status_code == 200, r.text
    return {"username": username, "password": password}


@pytest.fixture
def temp_user(client, auth):
    """Har bir test uchun alohida xodim — asosiy admin sessiyasiga tegmaslik uchun."""
    import uuid

    username = f"vaqtincha_{uuid.uuid4().hex[:8]}"
    password = "Vaqtincha-Parol-123"
    r = client.post("/auth/employees", headers=auth, json={
        "username": username, "password": password, "role": "cashier",
        "permissions": "pos", "full_name": "Test Xodim",
    })
    assert r.status_code == 200, r.text
    return {"id": r.json()["id"], "username": username, "password": password}


def _login(client, user):
    r = client.post("/auth/token", data={
        "username": user["username"], "password": user["password"], "force": "true",
    })
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_logout_actually_revokes_the_token(client, temp_user):
    """Ilgari chiqishdan keyin ham token 600 daqiqa ishlayverardi."""
    headers = _login(client, temp_user)

    assert client.get("/inventory/products", headers=headers).status_code == 200

    assert client.post("/auth/logout", headers=headers).status_code == 200

    after = client.get("/inventory/products", headers=headers)
    assert after.status_code == 401, (
        f"chiqishdan keyin token hali ham ishlayapti: {after.status_code}"
    )


def test_password_change_revokes_the_live_session(client, auth, temp_user):
    """Parol almashtirilsa, o'g'irlangan token darhol kuchini yo'qotsin."""
    headers = _login(client, temp_user)
    assert client.get("/inventory/products", headers=headers).status_code == 200

    r = client.patch(f"/auth/employees/{temp_user['id']}", headers=auth,
                     json={"password": "Yangi-Parol-456"})
    assert r.status_code == 200, r.text

    after = client.get("/inventory/products", headers=headers)
    assert after.status_code == 401, (
        f"parol almashtirilgandan keyin eski token ishlayapti: {after.status_code}"
    )


def test_second_login_invalidates_the_first_token(client, temp_user):
    """Bitta hisob - bitta sessiya: yangi kirish eskisini yopishi kerak."""
    first = _login(client, temp_user)
    second = _login(client, temp_user)

    assert client.get("/inventory/products", headers=second).status_code == 200
    assert client.get("/inventory/products", headers=first).status_code == 401


def test_invoice_upload_rejects_html(client, auth, confirmer):
    """Ilgari kengaytma fayl nomidan olinardi: .html yuklab, token o'g'irlash mumkin edi."""
    supplier = client.post("/suppliers/", headers=auth,
                           json={"name": "Test Firma", "phone": None, "address": None})
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["id"]

    r = client.post("/suppliers/receipts", headers=auth,
                    data={
                        "supplier_id": str(supplier_id), "total_amount": "1000",
                        "note": "test", "confirm_username": confirmer["username"],
                        "confirm_password": confirmer["password"],
                    },
                    files={"image": ("hujum.html", io.BytesIO(b"<script>alert(1)</script>"),
                                     "text/html")})
    assert r.status_code == 400, f"html fayl qabul qilindi: {r.status_code}"


def test_invoice_upload_accepts_an_image(client, auth, confirmer):
    supplier = client.post("/suppliers/", headers=auth,
                           json={"name": "Rasm Firma", "phone": None, "address": None})
    supplier_id = supplier.json()["id"]

    png = bytes.fromhex("89504e470d0a1a0a") + b"\x00" * 32
    r = client.post("/suppliers/receipts", headers=auth,
                    data={
                        "supplier_id": str(supplier_id), "total_amount": "2000",
                        "note": "rasm bilan", "confirm_username": confirmer["username"],
                        "confirm_password": confirmer["password"],
                    },
                    files={"image": ("nakladnoy.png", io.BytesIO(png), "image/png")})
    assert r.status_code == 200, r.text


def test_supplier_action_cannot_be_self_confirmed(client, auth):
    """Ikki kishilik nazorat: o'z amalini o'zi tasdiqlab bo'lmaydi.

    Ilgari verify_confirming_employee na rolni, na tasdiqlovchi boshqa odam
    ekanini tekshirardi — omborchi o'z parolini kiritib, o'zini tasdiqlardi.
    """
    supplier = client.post("/suppliers/", headers=auth,
                           json={"name": "O'z-o'zini tasdiq", "phone": None, "address": None})
    assert supplier.status_code == 200, supplier.text

    r = client.post("/suppliers/receipts", headers=auth, data={
        "supplier_id": str(supplier.json()["id"]), "total_amount": "5000",
        "note": "o'zim", "confirm_username": "miraziz",
        "confirm_password": "test-admin-password-123",
    })
    assert r.status_code == 403, f"o'zini o'zi tasdiqlab qo'ydi: {r.status_code}"


def test_proxy_headers_are_not_trusted_by_default():
    """Sozlanmagan holda X-Forwarded-For rate-limit kalitiga ta'sir qilmasin."""
    import core

    assert core.TRUST_PROXY_HEADERS is False, (
        "proksi sarlavhalariga sukut bo'yicha ishonilyapti — "
        "login chegarasini istalgan mijoz chetlab o'tadi"
    )
