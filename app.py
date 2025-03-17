# PicPerfect - Social Media Photo Optimizer
# A Python Flask web application for optimizing mobile photos for social media

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
import os
from werkzeug.utils import secure_filename
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import numpy as np
import io
import uuid
import time
import json

app = Flask(__name__)
app.secret_key = "picperfect_secret_key"
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['PROCESSED_FOLDER'] = 'processed'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

# Create necessary directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Image Processing Functions
def enhance_image(img, brightness=1.2, contrast=1.2, color=1.1, sharpness=1.3):
    """Basic image enhancement"""
    img = ImageEnhance.Brightness(img).enhance(brightness)
    img = ImageEnhance.Contrast(img).enhance(contrast)
    img = ImageEnhance.Color(img).enhance(color)
    img = ImageEnhance.Sharpness(img).enhance(sharpness)
    return img

def optimize_for_instagram(img, aspect_ratio="1:1"):
    """Optimize image for Instagram with specified aspect ratio"""
    width, height = img.size
    
    # Define aspect ratios
    ratios = {
        "1:1": (1, 1),      # Square
        "4:5": (4, 5),      # Portrait
        "16:9": (16, 9)     # Landscape
    }
    
    if aspect_ratio not in ratios:
        aspect_ratio = "1:1"  # Default to square
        
    target_w, target_h = ratios[aspect_ratio]
    
    # Calculate new dimensions while maintaining aspect ratio
    if (width / height) > (target_w / target_h):
        new_width = int(height * target_w / target_h)
        new_height = height
        left = (width - new_width) // 2
        top = 0
        right = left + new_width
        bottom = height
    else:
        new_width = width
        new_height = int(width * target_h / target_w)
        left = 0
        top = (height - new_height) // 2
        right = width
        bottom = top + new_height
    
    # Crop to desired aspect ratio
    img = img.crop((left, top, right, bottom))
    
    # Apply Instagram-like filter (basic enhancement)
    img = enhance_image(img)
    
    return img

def optimize_for_pinterest(img):
    """Optimize image for Pinterest (typically 2:3 vertical aspect ratio)"""
    width, height = img.size
    
    # Pinterest prefers vertical images with 2:3 aspect ratio
    target_w, target_h = 2, 3
    
    # Calculate new dimensions
    if (width / height) > (target_w / target_h):
        new_width = int(height * target_w / target_h)
        new_height = height
        left = (width - new_width) // 2
        top = 0
        right = left + new_width
        bottom = height
    else:
        new_width = width
        new_height = int(width * target_h / target_w)
        left = 0
        top = (height - new_height) // 2
        right = width
        bottom = top + new_height
    
    # Crop to desired aspect ratio
    img = img.crop((left, top, right, bottom))
    
    # Apply Pinterest-optimized enhancement
    img = enhance_image(img, brightness=1.1, contrast=1.3, color=1.2, sharpness=1.4)
    
    return img

def optimize_for_linkedin(img, content_type="post"):
    """Optimize image for LinkedIn with professional enhancements"""
    width, height = img.size
    
    # Define LinkedIn aspect ratios based on content type
    ratios = {
        "profile": (1, 1),         # Square for profile picture
        "post": (1200, 627),       # ~1.9:1 for post images
        "banner": (1584, 396)      # 4:1 for banner/cover images
    }
    
    if content_type not in ratios:
        content_type = "post"  # Default to post image ratio
        
    target_w, target_h = ratios[content_type]
    
    # Calculate new dimensions
    if (width / height) > (target_w / target_h):
        new_width = int(height * target_w / target_h)
        new_height = height
        left = (width - new_width) // 2
        top = 0
        right = left + new_width
        bottom = height
    else:
        new_width = width
        new_height = int(width * target_h / target_w)
        left = 0
        top = (height - new_height) // 2
        right = width
        bottom = top + new_height
    
    # Crop to desired aspect ratio
    img = img.crop((left, top, right, bottom))
    
    # Professional enhancement - more subtle than other platforms
    img = enhance_image(img, brightness=1.15, contrast=1.15, color=0.95, sharpness=1.2)
    
    # Lighten shadows for better face visibility
    # Create a slightly lightened version
    lightened = ImageEnhance.Brightness(img).enhance(1.3)
    
    # Create a mask from the dark areas of the original image
    # This helps identify shadow regions
    gray = img.convert('L')
    threshold = 100  # Adjust to control what's considered a shadow
    shadow_mask = gray.point(lambda x: 255 if x < threshold else 0)
    
    # Blend the original with the lightened version using the shadow mask
    shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(radius=5))
    shadow_mask = shadow_mask.convert('L')
    
    # Apply subtle vignette for professional look
    # Create mask for vignette
    if content_type != "banner":  # Don't apply vignette to banner images
        width, height = img.size
        mask = Image.new('L', (width, height), 255)
        
        # Generate radial gradient
        for y in range(height):
            for x in range(width):
                # Distance from center (0.0 to 1.0)
                distance = ((x - width/2)**2 + (y - height/2)**2)**0.5
                distance = distance / ((width/2)**2 + (height/2)**2)**0.5
                
                # Fall off from center (1.0) to edge (0.8)
                # The 0.8 value controls the darkness of the vignette
                mask.putpixel((x, y), int(max(255 * (1.0 - distance * 0.2), 0)))
        
        # Apply vignette mask
        img = ImageOps.multiply(img, mask.convert('RGB'))
    
    return img

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)
    
    file = request.files['file']
    platform = request.form.get('platform', 'instagram')
    aspect_ratio = request.form.get('aspect_ratio', '1:1')
    linkedin_type = request.form.get('linkedin_type', 'post')
    
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
        
    if file and allowed_file(file.filename):
        # Generate unique filename
        filename = str(uuid.uuid4()) + '_' + secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Process the image
        try:
            img = Image.open(filepath)
            
            if platform == 'instagram':
                processed_img = optimize_for_instagram(img, aspect_ratio)
            elif platform == 'pinterest':
                processed_img = optimize_for_pinterest(img)
            elif platform == 'linkedin':
                processed_img = optimize_for_linkedin(img, linkedin_type)
            else:
                # Default to Instagram if unknown platform
                processed_img = optimize_for_instagram(img, aspect_ratio)
            
            # Save processed image
            processed_filename = f"processed_{filename}"
            processed_filepath = os.path.join(app.config['PROCESSED_FOLDER'], processed_filename)
            processed_img.save(processed_filepath, quality=95)
            
            return jsonify({
                'status': 'success',
                'original': filename,
                'processed': processed_filename,
                'download_url': url_for('download_file', filename=processed_filename)
            })
            
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500
    
    return jsonify({
        'status': 'error',
        'message': 'Invalid file type. Please upload a JPG or PNG image.'
    }), 400

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['PROCESSED_FOLDER'], filename, as_attachment=True)

@app.route('/preview/<filename>')
def preview_file(filename):
    return send_from_directory(app.config['PROCESSED_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)
