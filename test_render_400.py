import requests
import json

URL = "https://kassa-1-pp1i.onrender.com/auth/token"
UPDATE_URL = "https://kassa-1-pp1i.onrender.com/auth/employees/1"

def test_update():
    # 1. Login to get token
    print("Loging in...")
    resp = requests.post(URL, data={"username": "admin", "password": "123"})
    if resp.status_code != 200:
        print(f"Login failed: {resp.text}")
        return
    
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Try to update phone or full_name
    print("Testing update...")
    update_data = {
        "full_name": "Admin User",
        "phone": "+998901234567",
        "role": "admin",
        "is_active": True
    }
    
    resp = requests.patch(UPDATE_URL, json=update_data, headers=headers)
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.text}")

if __name__ == "__main__":
    test_update()
