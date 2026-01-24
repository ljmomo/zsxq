import sys
import os
import time

# Add src to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.core.zsxq_api import ZSXQCore

def test_manual():
    print("Initializing Core...")
    core = ZSXQCore(
        download_dir="./downloads_test",
        user_data_dir="./browser_data/test_user"
    )
    
    print("Starting Browser...")
    try:
        core.start_browser(headless=False)
        print("Browser Started.")
        
        print("Checking Login Status...")
        is_logged_in = core.check_login_status()
        print(f"Logged in: {is_logged_in}")
        
        if not is_logged_in:
            print("Please login manually in the browser window...")
            # We wait a bit for potential manual login
            time.sleep(5)
            is_logged_in = core.check_login_status()
            print(f"Logged in after wait: {is_logged_in}")
        
        if is_logged_in:
            print("Fetching Subscriptions...")
            subs = core.get_subscriptions(scroll_attempts=2)
            for sub in subs:
                print(f" - {sub['name']}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        print("Closing...")
        core.close()

if __name__ == "__main__":
    test_manual()
