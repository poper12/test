from .utils import progress_for_pyrogram, autorenamefile
import os, time
import zipfile
from pyrogram import Client, filters
from pyrogram.types import Message
from PIL import Image
from models import cf, sync
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

from logger import logger

# Waiting List
cbz2pdf = {}

def delete_downloads_folders(base_path: str):
    """Delete all folders starting with 'downloads' in the specified base path."""
    try:
        for root, dirs, _ in os.walk(base_path):
            for dir_name in dirs:
                if dir_name.lower().startswith('downloads'):
                    folder_path = os.path.join(root, dir_name)
                    print(f"Removing directory: {folder_path}")
                    # Remove all files in the directory
                    for file in os.listdir(folder_path):
                        file_path = os.path.join(folder_path, file)
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                    # Remove the directory itself
                    os.rmdir(folder_path)
    except Exception as e:
        print(f"Error deleting folders: {e}")

def extract_images(zip_path: str, extract_to: str) -> list:
    """Extract images from a ZIP file and return a list of image file paths."""
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

    supported_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp')
    image_files = []

    for root, _, files in os.walk(extract_to):
        for name in files:
            file_path = os.path.join(root, name)
            if name.lower().endswith(supported_extensions):
                image_files.append(file_path)

    return image_files

def convert_webp_to_jpg(image_files: list) -> list:
    """Convert WebP images to JPEG format."""
    jpg_files = []
    for file_path in image_files:
        if file_path.lower().endswith('.webp'):
            with Image.open(file_path) as img:
                jpg_path = file_path.replace('.webp', '.jpg')
                img.convert('RGB').save(jpg_path, 'JPEG')
                jpg_files.append(jpg_path)
            os.remove(file_path)
        else:
            jpg_files.append(file_path)
    return jpg_files

def add_images_to_pdf(image_files: list, output_path: str):
    """Add images to a PDF file using ReportLab."""
    c = canvas.Canvas(output_path, pagesize=letter)

    for image in image_files:
        with Image.open(image) as img:
            width, height = img.size
            # Convert to points (1 point = 1/72 inch)
            width_pt = width * 72 / img.info.get('dpi', (72, 72))[0]
            height_pt = height * 72 / img.info.get('dpi', (72, 72))[1]
            c.setPageSize((width_pt, height_pt))
            c.drawImage(image, 0, 0, width=width_pt, height=height_pt)
            c.showPage()  # Create a new page for each image

    c.save()
    return output_path

def cleanup_files(*file_paths):
    """Remove specified files and directories."""
    for file_path in file_paths:
        try:
            if os.path.isdir(file_path):
                for root, _, files in os.walk(file_path, topdown=False):
                    for name in files:
                        os.remove(os.path.join(root, name))
                os.rmdir(file_path)
            elif os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Error cleaning up file {file_path}: {e}")


async def CBZ2PDF(client, message):
    user_id = message.from_user.id
    media = message.document 
    file_id = media.file_id
    new_name = media.file_name 
    file_size = media.file_size
    str_id = str(user_id)
    try:
        c_time = time.time()
        sts = await message.reply("<i>Downloading.....</i>")
        
        caption = cf.get(str_id, {}).get('caption', None)
        text = cf.get(str_id, {}).get('file_name', None)
        
        file_name = f"{new_name}.pdf" if not text else autorenamefile(new_name, text, None) + ".pdf"
        
        new_file = await client.download_media(
            file_id,
            file_name=f"{str(user_id)}/{new_name}", 
            progress=progress_for_pyrogram, 
            progress_args=("Download Started.....", sts, c_time))
        
        await sts.edit("<i>Converting....</i>")
        imageList = f'downloads/{user_id}'
        image_files = extract_images(new_file, imageList)
        image_files.sort()
        
        await sts.edit(f"<i>Total images found: {len(image_files)}</i>")
        if not image_files:
            await sts.edit('No images found in the .cbz file.')

        
        image_files = convert_webp_to_jpg(image_files)
        await sts.edit("`Converting Images Into PDF........`")
        f_banner = cf.get(str_id, {}).get('f_banner', None)
        l_banner = cf.get(str_id, {}).get('l_banner', None)
        
        if f_banner:
            f_banner_path = await client.download_media(f_banner, file_name=f"downloads/{user_id}/banner1.jpg")
            logger.info(f"{user_id} Banner Path => {f_banner_path}")
            image_files.insert(0, f_banner_path)
        
        if l_banner:
            l_banner_path = await client.download_media(l_banner, file_name=f"downloads/{user_id}/lastbanner.jpg")
            image_files.append(l_banner_path)
        
        pdf_output_path = add_images_to_pdf(image_files, file_name)
        
        thumb = cf.get(str_id, {}).get('thumb', None)
        ph_path = None 
        if thumb:
            await sts.edit("Adding Thumbnail....")
            ph_path = await client.download_media(thumb)
            Image.open(ph_path).convert("RGB").save(ph_path)
            img = Image.open(ph_path)
            img.resize((320, 320))
            img.save(ph_path, "JPEG")
        
        if caption: caption = caption.replace("{}", file_name)
        
        await client.send_document(user_id, 
                                   file_name=file_name,
                                   thumb=ph_path,
                                   caption=caption,
                                   document=pdf_output_path,
                                   progress=progress_for_pyrogram,
                                   progress_args=("Upload Started...", sts, time.time()))
        
        
        #if f_banner_path: os.remove(f_banner_path)
        #if l_banner_path: os.remove(l_banner_path)
        try: cleanup_files(new_file, pdf_output_path, imageList, ph_path)
        except: cleanup_files(new_file, pdf_output_path, imageList)
        
        await sts.delete()
    except Exception as e:
        await sts.edit(e)
        try: os.remove(new_file)
        except: pass
