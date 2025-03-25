# For Conerting
import os
import zipfile
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
import shutil

# For Bot
import time
from PIL import Image as PILImage
from datetime import datetime
from .utils import progress_for_pyrogram, autorenamefile
from models import cf, sync

from logger import logger

async def EPUB2PDF(client, message):
    user_id = message.from_user.id
    media = message.document 
    file_id = message.file_id
    new_name = message.file_name
    str_id = str(user_id)
    
    sts = await message.reply_text("<i>Downloading.....</i>")
    text = cf.get(str_id, {}).get('file_name', None)
    file_name = f"{new_name}.pdf" if not text else autorenamefile(new_name, text, None) + ".pdf"
    
    try:
        input_path = await client.download_media(
            file_id,
            file_name=file_name,
            progress=progress_for_pyrogram, 
            progress_args=("Download Started.....", sts, time.time()))
    except Exception as e:
        return await sts.edit(f"Errors AT Download {e}")
    
    OUPUTDIR = f"Downloads/{str(user_id)}/{new_name}"
    try:
        await sts.edit("<i>Converting....</i>")
        ZDIR = extract_epub(input_path, OUPUTDIR)
        
        ncx_file = get_ncx(ZDIR)
        
        title, htmlList = parse_ncx(ncx_file, ZDIR)
        htmlList.sort()
        
        await sts.edit("<i>Converting PDF....</i>")
        
        output_pdf_path = create_pdf(title, htmlList, file_name, None, None)
        
        caption = cf.get(str_id, {}).get('caption', None)
        thumb = cf.get(str_id, {}).get('thumb', None)
        ph_path = None
        if thumb:
            await sts.edit("<i>Adding Thumbnail....</i>")
            ph_path = await client.download_media(thumb)
            PILImage.open(ph_path).convert("RGB").save(ph_path)
            img = PILImage.open(ph_path)
            img.resize((320, 320))
            img.save(ph_path, "JPEG")
        
        if caption: caption = caption.replace("{}", file_name)
        
        await client.send_document(
            user_id,
            file_name=file_name,
            thumb=ph_path,
            caption=caption,
            document=output_pdf_path,
            progress=progress_for_pyrogram,
            progress_args=("Upload Started...", sts, time.time())
        )
        try: cleanup_files(input_path, output_pdf_path, ph_path)
        except: cleanup_files(input_path, output_pdf_path)
        
        cleanup(OUPUTDIR)
        
        if f_banner: os.remove(f_banner)
        if l_banner: os.remove(l_banner)
        
        await sts.delete()
    except Exception as e:
        await sts.edit(f"<i>{e}</i>")
        os.remove(input_path)
        cleanup(OUPUTDIR)


def cleanup(directory):
    """Removes the specified directory and its contents if it exists."""
    if os.path.exists(directory):
        shutil.rmtree(directory)  # Remove the directory and all its contents
        print(f"Cleaned up directory: {directory}")

def cleanup_files(*file_paths):
    """Removes specified files if they exist."""
    for file_path in file_paths:
        if os.path.exists(file_path):
            os.remove(file_path)  # Remove the file
            print(f"Removed file: {file_path}")
            
def extract_epub(epub_path, extract_to):
    """Extracts the EPUB file to a specified directory."""
    with zipfile.ZipFile(epub_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
        
    return extract_to


def parse_ncx(ncx_file, base_dir):
    chapters = []
    html_files = []
    title = ""
    tree = ET.parse(ncx_file)
    root = tree.getroot()

    # Namespace handling
    ns = {'ncx': 'http://www.daisy.org/z3986/2005/ncx/'}

    # Extract title
    docTitle = root.find('.//ncx:docTitle/ncx:text', ns)
    if docTitle is not None:
        title = docTitle.text

    # Extract chapters
    for navPoint in root.findall('.//ncx:navPoint', ns):
        content = navPoint.find('ncx:content', ns)
        if content is not None:
            src = content.get('src')
            chapters.append(src)

    file_names = [os.path.basename(name) for name in chapters]

    # Walk through the base directory to find matching files
    for root_dir, dirs, files in os.walk(base_dir):
        for file in files:
            if file in file_names:
                full_path = os.path.join(root_dir, file)
                html_files.append(full_path)

    return title, html_files

def create_pdf(title, file_list, output_pdf_path, banner1, banner2):
    pdf = SimpleDocTemplate(output_pdf_path, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    # Title style
    title_style = styles['Title']
    title_style.fontSize = 18
    title_style.leading = 24

    # Add title to PDF
    if title:
        title_paragraph = Paragraph(title, title_style)
        elements.append(title_paragraph)
        elements.append(Spacer(1, 20))  # Space after title

    # Normal text style
    styles['Normal'].fontSize = 14
    styles['Normal'].leading = 18
    
    if banner1:
        if os.path.exists(banner1):
            img_obj = Image(banner1)
            img_width, img_height = img_obj.wrap(0, 0)  # Get original dimensions

            # Resize image to fit within the page margins
            max_width = 800
            max_height = 600

            # Scale the image while maintaining aspect ratio
            if img_width > max_width or img_height > max_height:
                aspect_ratio = img_width / img_height
                if aspect_ratio > 1:  # Wider than tall
                    img_obj.width = max_width
                    img_obj.height = max_width / aspect_ratio
                else:  # Taller than wide
                    img_obj.height = max_height
                    img_obj.width = max_height * aspect_ratio
                
                img_obj.drawHeight = img_obj.height
                img_obj.drawWidth = img_obj.width

                elements.append(img_obj)
                elements.append(Spacer(1, 12))
    
    for xhtml_file in file_list:
        if os.path.exists(xhtml_file):
            with open(xhtml_file, 'r', encoding='utf-8') as file:
                content = file.read()
                soup = BeautifulSoup(content, 'html.parser')

                # Remove unwanted elements or text
                # Example: Remove all <div> elements with a specific class
                for unwanted_div in soup.find_all('div', class_='unwanted-class'):
                    unwanted_div.decompose()  # Remove the element from the tree

                # Example: Remove specific text patterns
                for p in soup.find_all('p'):
                    if "If you find any errors" in p.get_text():
                        p.decompose()  # Remove the paragraph containing the specific text

                # Extract text from paragraphs and divs
                for element in soup.body.find_all(['p', 'div']):
                    text = element.get_text(strip=True)
                    if text:  # Check if text is not empty
                        try:
                            # Clean the text to ensure it's well-formed
                            cleaned_text = BeautifulSoup(text, 'html.parser').get_text()

                            # Create a paragraph only if cleaned_text is valid
                            if cleaned_text:
                                paragraph = Paragraph(cleaned_text, styles['Normal'])
                                elements.append(paragraph)
                                elements.append(Spacer(1, 12))  # Space after each paragraph
                        except Exception as e:
                            print(f"Error creating paragraph for text: {text[:30]}...: {e}")

                # Extract images
                for img in soup.body.find_all('img'):
                    img_src = img['src']
                    img_path = os.path.join(os.path.dirname(xhtml_file), img_src)  # Construct full image path
                    if os.path.exists(img_path):
                        img_obj = Image(img_path)
                        img_width, img_height = img_obj.wrap(0, 0)  # Get original dimensions

                        # Resize image to fit within the page margins
                        max_width = 800
                        max_height = 600

                        # Scale the image while maintaining aspect ratio
                        if img_width > max_width or img_height > max_height:
                            aspect_ratio = img_width / img_height
                            if aspect_ratio > 1:  # Wider than tall
                                img_obj.width = max_width
                                img_obj.height = max_width / aspect_ratio
                            else:  # Taller than wide
                                img_obj.height = max_height
                                img_obj.width = max_height * aspect_ratio

                        # Set the image dimensions
                        try:
                            img_obj.drawHeight = img_obj.height
                            img_obj.drawWidth = img_obj.width

                            elements.append(img_obj)
                            elements.append(Spacer(1, 12))  # Space after each image
                        except Exception as e:
                            print(f"Error adding image '{img_src}': {e}")
        else:
            print(f"File not found: {xhtml_file}")
    
    if banner2:
        if os.path.exists(banner2):
            img_obj = Image(banner2)
            img_width, img_height = img_obj.wrap(0, 0)  # Get original dimensions

            # Resize image to fit within the page margins
            max_width = 800
            max_height = 600

            # Scale the image while maintaining aspect ratio
            if img_width > max_width or img_height > max_height:
                aspect_ratio = img_width / img_height
                if aspect_ratio > 1:  # Wider than tall
                    img_obj.width = max_width
                    img_obj.height = max_width / aspect_ratio
                else:  # Taller than wide
                    img_obj.height = max_height
                    img_obj.width = max_height * aspect_ratio
                
                img_obj.drawHeight = img_obj.height
                img_obj.drawWidth = img_obj.width

                elements.append(img_obj)
                elements.append(Spacer(1, 12))

    pdf.build(elements)

    return output_pdf_path


def get_ncx(temp_dir):
    ncx_file = None
    for root, dirs, files in os.walk(temp_dir):
        for file in files:
            if file.endswith('.ncx'):
                ncx_file = os.path.join(root, file)
                return ncx_file
    
