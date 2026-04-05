import os
import glob
import zipfile
import subprocess
import shutil
import cv2
from tqdm import tqdm

DATASET_DIR = "asl_dataset"
TRAIN_DIR = os.path.join(DATASET_DIR, "train")

# Define target classes (A-Z)
TARGET_CLASSES = [chr(i) for i in range(ord('A'), ord('Z') + 1)]

# The Kaggle dataset ID we'll use (Grassknoted ASL Alphabet)
# It contains 87,000 images, easily covering the 50,000 requirement.
KAGGLE_DATASET = "grassknoted/asl-alphabet"
ARCHIVE_NAME = "asl-alphabet.zip"
DOWNLOAD_DIR = "temp_downloads"

def download_dataset():
    """Downloads the dataset using the Kaggle API."""
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
        
    print("Downloading ASL Alphabet Dataset from Kaggle...")
    try:
        subprocess.run(["kaggle", "datasets", "download", "-d", KAGGLE_DATASET, "-p", DOWNLOAD_DIR], check=True)
    except FileNotFoundError:
        print("Kaggle CLI not found. Please ensure 'kaggle' is installed and in your PATH.")
        raise
    except subprocess.CalledProcessError:
        print("Failed to download dataset. Ensure your kaggle.json credentials are set up in ~/.kaggle/")
        raise

def extract_dataset():
    """Extracts the downloaded zip file."""
    archive_path = os.path.join(DOWNLOAD_DIR, ARCHIVE_NAME)
    extract_path = os.path.join(DOWNLOAD_DIR, "extracted")
    
    if os.path.exists(archive_path):
        print(f"Extracting {archive_path}...")
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
    return extract_path

def setup_directories():
    """Builds the final ASL dataset structure."""
    if not os.path.exists(TRAIN_DIR):
        os.makedirs(TRAIN_DIR)
    for letter in TARGET_CLASSES:
        os.makedirs(os.path.join(TRAIN_DIR, letter), exist_ok=True)

def process_and_merge(extract_path):
    """Resizes, cleans, and merges images into the structured format."""
    print("Processing images...")
    
    # Search for all jpg/png files within the extracted Kaggle directory
    search_path_jpg = os.path.join(extract_path, "**", "*.jpg")
    search_path_png = os.path.join(extract_path, "**", "*.png")
    all_images = glob.glob(search_path_jpg, recursive=True) + glob.glob(search_path_png, recursive=True)
    
    class_counts = {c: 0 for c in TARGET_CLASSES}
    
    for img_path in tqdm(all_images, desc="Processing Images A-Z"):
        dirname = os.path.basename(os.path.dirname(img_path)).upper()
        
        # Ignore non-letter classes like 'space', 'nothing', 'del'
        if dirname not in TARGET_CLASSES:
            continue
            
        # Read the image
        img = cv2.imread(img_path)
        if img is None:
            continue # Skip corrupted files
            
        # Resize to exactly 224x224 and ensure standard RGB encoding
        img_resized = cv2.resize(img, (224, 224))
        
        # Save to final train directory with unique name formatting
        count = class_counts[dirname]
        new_filename = f"{dirname}_{count:05d}.jpg"
        save_path = os.path.join(TRAIN_DIR, dirname, new_filename)
        
        cv2.imwrite(save_path, img_resized)
        class_counts[dirname] += 1

    return class_counts

def get_dir_size(path='.'):
    """Calculates final nested directory size."""
    total = 0
    with os.scandir(path) as it:
        for entry in it:
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += get_dir_size(entry.path)
    return total

def print_summary(class_counts):
    """Prints the final comprehensive statistical report."""
    print("\n" + "="*50)
    print("DATASET BUILT SUCCESSFULLY")
    print("="*50)
    
    total_images = sum(class_counts.values())
    print(f"Total images: {total_images}\n")
    
    for c in TARGET_CLASSES:
        print(f"{c}: {class_counts[c]}")
        
    size_bytes = get_dir_size(DATASET_DIR)
    size_mb = size_bytes / (1024 * 1024)
    size_gb = size_mb / 1024
    
    if size_gb >= 1.0:
        print(f"\nDataset size: {size_gb:.2f} GB")
    else:
        print(f"\nDataset size: {size_mb:.2f} MB")

def cleanup():
    """Removes the gigabytes of temporary zip files used in processing."""
    print("Cleaning up temporary downloaded files...")
    if os.path.exists(DOWNLOAD_DIR):
        shutil.rmtree(DOWNLOAD_DIR)

def main():
    try:
        setup_directories()
        download_dataset()
        extract_path = extract_dataset()
        class_counts = process_and_merge(extract_path)
        cleanup()
        print_summary(class_counts)
    except Exception as e:
        print(f"\n[ERROR] Pipeline Aborted: {e}")
        print("Are you missing your Kaggle API key? Ensure 'kaggle.json' is configured!")

if __name__ == "__main__":
    main()
