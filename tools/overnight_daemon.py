import time
import subprocess
import os

def run_scanners():
    print("Running scanners...")
    subprocess.run(["python", "src/run_scanners.py", "--generated", "data/generated", "--results", "data/scan_results"], check=False)
    subprocess.run(["python", "src/parse_results.py"], check=False)

def main():
    print("Starting overnight watcher daemon...")
    while True:
        run_scanners()
        print("Sleeping for 30 minutes...")
        time.sleep(1800)

if __name__ == '__main__':
    main()
