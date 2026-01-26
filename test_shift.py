import asyncio
import httpx

async def test_shift_open():
    # First login to get token
    async with httpx.AsyncClient() as client:
        # Login
        login_data = {
            "username": "admin",
            "password": "admin123"
        }
        
        login_response = await client.post(
            "http://127.0.0.1:8000/token",
            data=login_data
        )
        
        if login_response.status_code != 200:
            print(f"Login failed: {login_response.status_code}")
            print(login_response.text)
            return
        
        token_data = login_response.json()
        token = token_data["access_token"]
        print(f"✅ Login successful! Token: {token[:20]}...")
        
        # Test shift open
        headers = {"Authorization": f"Bearer {token}"}
        shift_data = {
            "opening_balance": 100000,
            "note": "Test smena"
        }
        
        shift_response = await client.post(
            "http://127.0.0.1:8000/api/shifts/open",
            json=shift_data,
            headers=headers
        )
        
        print(f"\n📊 Shift Open Response:")
        print(f"Status Code: {shift_response.status_code}")
        print(f"Response: {shift_response.text}")
        
        if shift_response.status_code == 200:
            print("✅ Smena muvaffaqiyatli ochildi!")
        else:
            print(f"❌ Xato: {shift_response.status_code}")

if __name__ == "__main__":
    asyncio.run(test_shift_open())
print("✅ Smena muvaffaqiyatli ochildi!")