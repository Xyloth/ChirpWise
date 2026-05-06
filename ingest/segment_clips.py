from birdtrainer.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["segment-clips", *(__import__("sys").argv[1:])]))

