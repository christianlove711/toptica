if __name__ == "__main__":
    try:
        from toptica_lab.main import main
    except ImportError as exc:
        missing = getattr(exc, "name", "dependency")
        print(
            f"Failed to start the app because '{missing}' is not installed.\n"
            "Install dependencies with: pip install -r requirements.txt"
        )
        raise SystemExit(1) from exc

    raise SystemExit(main())
