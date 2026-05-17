import zipfile
import glob

def check_zip():
    zip_files = glob.glob(r'C:\Users\tony9\Downloads\test area\**\*.zip', recursive=True)
    if not zip_files:
        print("Zip not found")
        return
    zpath = zip_files[0]
    print(f"Reading {zpath}".encode('utf-8').decode('cp950', 'ignore'))
    with zipfile.ZipFile(zpath, 'r') as z:
        for info in z.infolist():
            name = info.filename.encode('utf-8').decode('cp950', 'ignore')
            if 'run' in name.lower() or 'forge' in name.lower() or 'server' in name.lower() or '.bat' in name.lower() or '.sh' in name.lower() or '.jar' in name.lower():
                # only print root level or interesting ones to save space
                if '/' not in name or name.count('/') == 1:
                    print(name)

if __name__ == "__main__":
    check_zip()
