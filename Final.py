import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from zipfile import ZipFile
from PIL import Image
import re
from transformers import pipeline

# Function to convert Google Drive link to direct download link
def convert_drive_link(link):
    match = re.search(r'/d/([^/]+)', link)
    if match:
        file_id = match.group(1)
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    return link

# Function to download an image from a URL
def download_image(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.content
    return None

# Function to resize image to a specific size
def resize_image(image_content, size=(1024, 1024)):
    image = Image.open(BytesIO(image_content))
    image = image.resize(size)
    if image.mode == 'RGBA':
        image = image.convert('RGB')
    img_byte_arr = BytesIO()
    image.save(img_byte_arr, format='JPEG')
    return img_byte_arr.getvalue()

# Function to remove background from an image
def remove_background(image_content):
    image = Image.open(BytesIO(image_content))
    pipe = pipeline("image-segmentation", model="briaai/RMBG-1.4", trust_remote_code=True)
    output_img = pipe(image)
    img_byte_arr = BytesIO()
    output_img.save(img_byte_arr, format='PNG')
    return img_byte_arr.getvalue()

# Function to combine the foreground image with a background image
def combine_with_background(foreground_content, background_content, resize_foreground=False):
    foreground = Image.open(BytesIO(foreground_content)).convert("RGBA")
    background = Image.open(BytesIO(background_content)).convert("RGBA")
    background = background.resize((1024, 1024))
    
    if resize_foreground:
        # Calculate the scaling factor
        
        k = (400000 / int((foreground.width * foreground.height))) ** 0.5
             
        foreground_size = (int((foreground.width) * k), int((foreground.height) * k))  # Resize to 50% of background
        foreground = foreground.resize(foreground_size)

    # Center the foreground on the background
    fg_width, fg_height = foreground.size
    bg_width, bg_height = background.size
    position = ((bg_width - fg_width) // 2, (bg_height - fg_height) // 2)
    
    combined = background.copy()
    combined.paste(foreground, position, foreground)
    img_byte_arr = BytesIO()
    combined.save(img_byte_arr, format='PNG')
    return img_byte_arr.getvalue()

# Function to download all images as a ZIP file
def download_all_images_as_zip(images_info, remove_bg=False, add_bg=False, bg_image=None, resize_foreground=False):
    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, 'w') as zf:
        for name, url in images_info:
            url = convert_drive_link(url)
            image_content = download_image(url)
            if image_content:
                if remove_bg:
                    processed_image = remove_background(image_content)
                    ext = 'png'
                else:
                    processed_image = resize_image(image_content)
                    ext = 'jpeg'
                
                if add_bg and bg_image:
                    processed_image = combine_with_background(processed_image, bg_image, resize_foreground=resize_foreground)
                    ext = 'png'
                
                zf.writestr(f"{name}.{ext}", processed_image)
    zip_buffer.seek(0)
    return zip_buffer

# Streamlit UI
st.title("Image Downloader")

# Option to choose between uploading an Excel file or images
upload_option = st.radio("Select upload option:", ("Excel file", "Images"))

if upload_option == "Excel file":
    uploaded_file = st.file_uploader("Upload an Excel or CSV file", type=["xlsx", "csv"])
    
    if uploaded_file:
        if uploaded_file.name.endswith('.xlsx'):
            df = pd.read_excel(uploaded_file)
        else:
            df = pd.read_csv(uploaded_file)
        
        if 'links' in df.columns and 'name' in df.columns:
            df.dropna(subset=['links'], inplace=True)
            images_info = list(zip(df['name'], df['links']))
            
            remove_bg = st.checkbox("Remove background from images")
            add_bg = st.checkbox("Add background to images")
            resize_fg = st.checkbox("Resize foreground image to center on background")

            bg_image = None
            if add_bg:
                bg_file = st.file_uploader("Upload background image", type=["jpg", "jpeg", "png"])
                if bg_file:
                    bg_image = resize_image(bg_file.read())

            if st.button("Download All Images"):
                zip_buffer = download_all_images_as_zip(images_info, remove_bg=remove_bg, add_bg=add_bg, bg_image=bg_image, resize_foreground=resize_fg)
                st.download_button(
                    label="Download All Images as ZIP",
                    data=zip_buffer,
                    file_name="all_images.zip",
                    mime="application/zip"
                )

            # Display images in two columns
            cols = st.columns(2)
            for i, (name, url) in enumerate(images_info):
                col = cols[i % 2]
                with col:
                    url = convert_drive_link(url)
                    image_content = download_image(url)
                    if image_content:
                        if remove_bg:
                            processed_image = remove_background(image_content)
                            ext = 'png'
                        else:
                            processed_image = resize_image(image_content)
                            ext = 'jpeg'
                        
                        if add_bg and bg_image:
                            processed_image = combine_with_background(processed_image, bg_image, resize_foreground=resize_fg)
                            ext = 'png'
                        
                        st.image(processed_image, caption=name)
                        st.download_button(
                            label=f"Download {name}",
                            data=processed_image,
                            file_name=f"{name}.{ext}",
                            mime=f"image/{ext}"
                        )
        else:
            st.error("The uploaded file must contain 'links' and 'name' columns.")
elif upload_option == "Images":
    uploaded_files = st.file_uploader("Upload images", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    
    if uploaded_files:
        remove_bg = st.checkbox("Remove background from images")
        add_bg = st.checkbox("Add background to images")
        resize_fg = st.checkbox("Resize foreground image to center on background")

        bg_image = None
        if add_bg:
            bg_file = st.file_uploader("Upload background image", type=["jpg", "jpeg", "png"])
            if bg_file:
                bg_image = resize_image(bg_file.read())

        images_info = [(file.name, file) for file in uploaded_files]

        if st.button("Download All Images"):
            zip_buffer = BytesIO()
            with ZipFile(zip_buffer, 'w') as zf:
                for name, file in images_info:
                    image_content = file.read()
                    if remove_bg:
                        processed_image = remove_background(image_content)
                        ext = 'png'
                    else:
                        processed_image = resize_image(image_content)
                        ext = 'jpeg'
                    
                    if add_bg and bg_image:
                        processed_image = combine_with_background(processed_image, bg_image, resize_foreground=resize_fg)
                        ext = 'png'
                    
                    zf.writestr(f"{name}.{ext}", processed_image)
            zip_buffer.seek(0)
            st.download_button(
                label="Download All Images as ZIP",
                data=zip_buffer,
                file_name="all_images.zip",
                mime="application/zip"
            )

        # Display images in two columns
        cols = st.columns(2)
        for i, (name, file) in enumerate(images_info):
            col = cols[i % 2]
            with col:
                image_content = file.read()
                if remove_bg:
                    processed_image = remove_background(image_content)
                    ext = 'png'
                else:
                    processed_image = resize_image(image_content)
                    ext = 'jpeg'
                
                if add_bg and bg_image:
                    processed_image = combine_with_background(processed_image, bg_image, resize_foreground=resize_fg)
                    ext = 'png'
                
                st.image(processed_image, caption=name)
                st.download_button(
                    label=f"Download {name}",
                    data=processed_image,
                    file_name=f"{name}.{ext}",
                    mime=f"image/{ext}"
                )
