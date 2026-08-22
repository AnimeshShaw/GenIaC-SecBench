import os
import argparse
from huggingface_hub import snapshot_download

def main():
    parser = argparse.ArgumentParser(description="Download the benchmark dataset from Hugging Face.")
    parser.add_argument('--repo-id', type=str, default='AnimeshShaw/GenIaC-SecBench', help='Hugging Face dataset repository ID')
    args = parser.parse_args()

    print(f"Downloading dataset from Hugging Face: {args.repo_id}...")
    
    # Download the dataset directly into the local data/ folder
    local_dir = os.path.join(os.getcwd(), 'data')
    os.makedirs(local_dir, exist_ok=True)
    
    try:
        snapshot_download(repo_id=args.repo_id, repo_type='dataset', local_dir=local_dir)
        print("\nDataset successfully downloaded and extracted to the 'data/' directory!")
    except Exception as e:
        print(f"\nError downloading dataset: {e}")
        print("Make sure you have replaced 'AnimeshShaw/GenIaC-SecBench' with your actual Hugging Face repo ID in the script.")

if __name__ == '__main__':
    main()
