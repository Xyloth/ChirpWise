from birdtrainer.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["import-taxonomy", *(__import__("sys").argv[1:])]))

