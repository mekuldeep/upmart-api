import requests

def test_login():
    url = "https://8b54-2401-4900-5dd3-8eea-49d1-6f02-59d1-4b17.ngrok-free.app/api/admin/login"
    payload = {
        "email": "admin@upmart.com",
        "password": "12345678"
    }
    try:
        response = requests.post(url, json=payload)
        print(f"Status: {response.status_code}")
        print(f"Body: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_login()
