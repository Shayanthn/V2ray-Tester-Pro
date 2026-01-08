import os
import sys
import zipfile
import requests
import shutil
import stat

def download_xray():
    version = "v1.8.6"
    
    if sys.platform.startswith('win'):
        filename = "Xray-windows-64.zip"
        executable_name = "xray.exe"
    elif sys.platform.startswith('linux'):
        filename = "Xray-linux-64.zip"
        executable_name = "xray"
    elif sys.platform.startswith('darwin'): # macOS
        filename = "Xray-macos-64.zip"
        executable_name = "xray"
    else:
        print(f"❌ Unsupported platform: {sys.platform}")
        return

    url = f"https://github.com/XTLS/Xray-core/releases/download/{version}/{filename}"
    
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
        
        if os.path.exists(filename):
            os.remove(filename)
            print("Cleaned up zip file.")
        
        if os.path.exists(executable_name):
            print(f"✅ {executable_name} is ready.")
            
            # Set executable permissions on Linux/macOS
            if not sys.platform.startswith('win'):
                st = os.stat(executable_name)
                os.chmod(executable_name, st.st_mode | stat.S_IEXEC)
                print(f"✅ Executable permissions set for {executable_name}.")
        else:
            print(f"❌ {executable_name} not found after extraction.")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    download_xray()
