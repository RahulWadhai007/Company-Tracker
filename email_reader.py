from src.email_reader import check_unread_email_count

if __name__ == "__main__":
    try:
        check_unread_email_count()
        print("Script finished!")
    except Exception as e:
        print(f"❌ An error occurred: {e}")
