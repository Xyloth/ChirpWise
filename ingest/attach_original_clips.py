from birdtrainer.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["attach-original-clips", *(__import__("sys").argv[1:])]))

