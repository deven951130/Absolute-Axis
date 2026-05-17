import shutil
import glob
import os

def copy_zip():
    zips = glob.glob(r'C:\Users\tony9\Downloads\test area\**\*.zip', recursive=True)
    if zips:
        src = zips[0]
        dst = r'e:\absolute axis\scratch\mc_temp.zip'
        print(f"Copying {src.encode('utf-8').decode('cp950', 'ignore')} to {dst}")
        shutil.copy2(src, dst)
        print("Done!")
    else:
        print("Zip not found.")

if __name__ == "__main__":
    copy_zip()
