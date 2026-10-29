from app import User, create_user, init_db

password = "qsenpKRvWjyYsu9T9PTyg"


def main() -> None:
    init_db()

    existing = User.get_or_none(User.username == "theresa")
    if existing:
        print(f"theresa already exists.")
        return

    create_user(username="theresa", password=password)
    print(f"Created theresa")


if __name__ == "__main__":
    main()
