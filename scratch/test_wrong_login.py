import requests

def test_login_wrong_password():
    url = "https://e754-223-189-94-138.ngrok-free.app/api/admin/login"
    payload = {
        "email": "admin@upmart.com",
        "password": "123456878" # Extra '8'
    }
    try:
        response = requests.post(url, json=payload)
        print(f"Status: {response.status_code}")
        print(f"Body: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_login_wrong_password()
