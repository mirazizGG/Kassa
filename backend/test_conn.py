import http.client

def test():
    print("Connecting to 127.0.0.1:8000...")
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=10)
    try:
        conn.request("GET", "/")
        res = conn.getresponse()
        print(f"Status: {res.status}")
        print(f"Body: {res.read()}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    test()
