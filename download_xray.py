import os
import zipfile
import requests
import shutil

def download_xray():
    url = "https://github.com/XTLS/Xray-core/releases/download/v1.8.6/Xray-windows-64.zip"
    filename = "Xray-windows-64.zip"
    
    print(f"Downloading {filename} from {url}...")
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("Download complete.")
        
        print("Extracting...")
        with zipfile.ZipFile(filename, 'r') as zip_ref:
            zip_ref.extractall(".")
        print("Extraction complete.")
        
        os.remove(filename)
        print("Cleaned up zip file.")
        
        if os.path.exists("xray.exe"):
            print("✅ xray.exe is ready.")
        else:
            print("❌ xray.exe not found after extraction.")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    download_xray()
