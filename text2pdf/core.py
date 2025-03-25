from PIL import Image as IMG
from logger import logger

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
import shutil, os




def text2pdf(file_list, output_pdf_path, banner1, banner2):
    output_pdf_path = f"{output_pdf_path}.pdf"
    pdf = SimpleDocTemplate(output_pdf_path, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

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
    
    for ctext in file_list:
        paragraph = Paragraph(ctext, styles['Normal'])
        elements.append(paragraph)
        elements.append(Spacer(1, 12))
    
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
    
    if banner1: os.remove(banner1)
    if banner2: os.remove(banner2)
    
    pdf.build(elements)

    return output_pdf_path

