from utils.auth import verify_password, get_password_hash

def test_auth():
    password = "12345678"
    hashed = "$2b$12$/K1/xBDM9gFhfM/npZfhNeHrsXIegDVUrTVTBHBOlxQhHOd90rHXa"
    
    print(f"Testing password: {password}")
    print(f"Against hash: {hashed}")
    
    try:
        result = verify_password(password, hashed)
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error during verify: {e}")
        import traceback
        traceback.print_exc()

    print("\nGenerating new hash...")
    new_hash = get_password_hash(password)
    print(f"New hash: {new_hash}")
    print(f"Verifying new hash: {verify_password(password, new_hash)}")

if __name__ == "__main__":
    test_auth()
