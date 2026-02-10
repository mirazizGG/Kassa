
import requests
import time

API_URL = "http://localhost:8000"

def test_rate_limiting():
    print("\n--- Testing Rate Limiting (Login) ---")
    for i in range(7):
        response = requests.post(f"{API_URL}/auth/token", data={"username": "admin", "password": "123"})
        if response.status_code == 429:
            print(f"Success: Request {i+1} was blocked (Rate Limit hit!)")
            return
        else:
            print(f"Request {i+1}: {response.status_code} (Allowed)")
    print("Failure: Rate limit was not hit.")

def test_phone_validation():
    print("\n--- Testing Phone Number Validation ---")
    # Wrong format (missing +)
    data = {
        "username": "testuser",
        "password": "password123",
        "role": "cashier",
        "phone": "998901234567" 
    }
    # This usually requires an auth token to create an employee, 
    # but we can check if the schema validation works by trying to login with bad data structures if endpoint allowed.
    # For now, let's just explain this is better tested via UI or a dedicated script.
    print("To test validation, try adding a client in the UI with a phone number that doesn't start with +998.")

if __name__ == "__main__":
    try:
        test_rate_limiting()
    except Exception as e:
        print(f"Error: {e}. Is the server running?")
