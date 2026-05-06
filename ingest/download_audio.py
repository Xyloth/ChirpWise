from birdtrainer.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["download-audio", *(__import__("sys").argv[1:])]))

