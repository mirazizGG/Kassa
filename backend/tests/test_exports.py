"""Hisobot yuklab olish yo'llari.

pandas/openpyxl sinxron ishlaydi. Ilgari ular to'g'ridan-to'g'ri async
handlerda chaqirilardi va butun event loop'ni ushlab turardi: admin hisobot
yuklab olayotganda hamma kassa kutib qolardi. Endi asyncio.to_thread ichida.
Bu testlar refaktordan keyin yo'llar ishlashda davom etayotganini tekshiradi.
"""
import io

import pytest

openpyxl = pytest.importorskip("openpyxl")


def test_sales_xlsx_export_downloads(client, auth):
    r = client.get("/finance/export-sales-excel", headers=auth)
    assert r.status_code == 200, r.text
    assert "spreadsheetml" in r.headers["content-type"]
    assert r.headers["content-disposition"].startswith("attachment;")

    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Savdolar"]


def test_audit_xlsx_export_downloads(client, auth):
    r = client.get("/audit/export-excel", headers=auth)
    assert r.status_code == 200, r.text
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["AuditLog"]

    rows = list(wb["AuditLog"].iter_rows(values_only=True))
    assert rows and rows[0][:3] == ("ID", "Sana", "Xodim")


def test_sales_csv_export_downloads(client, auth):
    r = client.get("/finance/export-sales", headers=auth)
    assert r.status_code == 200, r.text
    assert r.headers["content-disposition"].startswith("attachment;")
    assert r.content, "bo'sh CSV"


def test_audit_export_is_admin_only(client, auth, temp_user_factory):
    """Audit jurnali - faqat admin uchun, eksport ham."""
    headers = temp_user_factory("cashier")
    r = client.get("/audit/export-excel", headers=headers)
    assert r.status_code == 403, f"kassir audit eksportini oldi: {r.status_code}"


def test_csv_safe_neutralises_spreadsheet_formulas():
    """Mijoz ismi Telegram orqali kiritiladi - u formula bo'lib bajarilmasin.

    Excel "=", "+", "-", "@" bilan boshlangan katakni formula deb o'qiydi.
    Ilgari bunday matn hisobotga o'zgarishsiz tushardi va faylni ochgan
    admin kompyuterida bajarilardi.
    """
    from routers.audit import csv_safe

    assert csv_safe("=cmd|'/c calc'!A1").startswith("'"), "formula neytrallanmadi"
    assert csv_safe("+1+1").startswith("'")
    assert csv_safe("-2").startswith("'")
    assert csv_safe("@SUM(A1)").startswith("'")
    assert csv_safe("Oddiy mijoz") == "Oddiy mijoz", "oddiy matn buzildi"
    assert csv_safe(None) == ""
    assert csv_safe(1500) == "1500"


def test_csv_export_contains_no_raw_formula(client, auth):
    c = client.post("/crm/clients", headers=auth,
                    json={"name": "=1+1", "phone": "+998901112255"})
    assert c.status_code == 200, c.text

    r = client.get("/finance/export-sales", headers=auth)
    assert r.status_code == 200
    body = r.content.decode("utf-8", "replace")
    for line in body.splitlines():
        for cell in line.split(","):
            assert not cell.strip().startswith("="), f"xom formula: {cell!r}"


def test_refunded_sales_are_excluded_from_employee_kpi(client, auth):
    """Chek urib keyin bekor qilgan kassir halolidan yuqori ko'rsatkich olmasin."""
    p = client.post("/inventory/products", headers=auth, json={
        "name": "KPI testi", "barcode": "TEST-KPI-1", "buy_price": 100.0,
        "sell_price": 7_000.0, "stock": 20.0, "is_infinite": False,
        "unit": "dona", "category_id": None, "is_favorite": False,
    }).json()

    client.post("/pos/shifts/open", headers=auth, json={"opening_balance": 0})
    sale = client.post("/sales/", headers=auth, json={
        "total_amount": 7_000.0, "payment_method": "cash",
        "items": [{"product_id": p["id"], "quantity": 1, "price": 7_000.0}],
        "cash_amount": 7_000.0,
    })
    assert sale.status_code == 200, sale.text

    def _my_total():
        rows = client.get("/finance/employee-performance", headers=auth).json()
        me = next(r for r in rows if r["username"] == "miraziz")
        return me["sale_total"]

    before = _my_total()

    r = client.post(f"/sales/{sale.json()['id']}/refund", headers=auth,
                    json={"manager_username": "miraziz",
                          "manager_password": "test-admin-password-123"})
    assert r.status_code == 200, r.text

    after = _my_total()
    assert after == before - 7_000.0, (
        f"vozvrat KPI dan chiqmadi: {before} -> {after}"
    )


def test_exports_label_refunded_receipts(client, auth):
    """Fayl dashboard bilan farq qilsa, sababi fayldan KO'RINISHI kerak."""
    r = client.get("/finance/export-sales", headers=auth)
    assert r.status_code == 200
    body = r.content.decode("utf-8", "replace")
    header = body.splitlines()[0]
    assert "Holat" in header, f"holat ustuni yo'q: {header}"
    assert "Qaytarilgan" in body, "qaytarilgan cheklar belgilanmagan"
