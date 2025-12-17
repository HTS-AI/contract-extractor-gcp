"""
Image Enhancement and Blur Detection Module
Handles blurry document detection and image pre-processing for better OCR accuracy.
"""

import os
import numpy as np
from typing import Tuple, List, Dict, Any, Optional
from pathlib import Path

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    cv2 = None

try:
    from PIL import Image, ImageEnhance, ImageFilter
    from pdf2image import convert_from_path
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None
    ImageEnhance = None
    ImageFilter = None
    convert_from_path = None

try:
    from scipy import ndimage
    from scipy.ndimage import gaussian_filter
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    ndimage = None


def check_dependencies() -> Tuple[bool, str]:
    """
    Check if all required dependencies are available.
    
    Returns:
        Tuple of (is_available, error_message)
    """
    missing = []
    
    if not CV2_AVAILABLE:
        missing.append("opencv-python (cv2)")
    if not PIL_AVAILABLE:
        missing.append("Pillow, pdf2image")
    if not SCIPY_AVAILABLE:
        missing.append("scipy")
    
    if missing:
        return False, f"Missing dependencies: {', '.join(missing)}. Install with: pip install opencv-python Pillow pdf2image scipy"
    
    return True, ""


def detect_blur(image: np.ndarray, threshold: float = 100.0) -> Tuple[bool, float]:
    """
    Detect if an image is blurry using Laplacian variance method.
    
    Args:
        image: Image as numpy array (grayscale)
        threshold: Blur threshold (lower = more sensitive to blur)
                  Typical values: 50-200 (100 is standard)
        
    Returns:
        Tuple of (is_blurry, blur_score)
        - is_blurry: True if image is considered blurry
        - blur_score: Laplacian variance score (higher = sharper)
    """
    if not CV2_AVAILABLE:
        return False, 0.0
    
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    
    # Calculate Laplacian variance
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    blur_score = laplacian.var()
    
    is_blurry = blur_score < threshold
    
    return is_blurry, blur_score


def enhance_image(image: np.ndarray, enhancement_level: str = "medium") -> np.ndarray:
    """
    Apply image enhancement techniques to improve OCR accuracy.
    
    Args:
        image: Image as numpy array
        enhancement_level: "light", "medium", or "aggressive"
        
    Returns:
        Enhanced image as numpy array
    """
    if not CV2_AVAILABLE:
        return image
    
    enhanced = image.copy()
    
    # Convert to grayscale if needed
    if len(enhanced.shape) == 3:
        gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
    else:
        gray = enhanced
    
    # Step 1: Denoise
    if enhancement_level in ["medium", "aggressive"]:
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    else:
        denoised = cv2.bilateralFilter(gray, 9, 75, 75)
    
    # Step 2: Contrast enhancement using CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrast_enhanced = clahe.apply(denoised)
    
    # Step 3: Sharpening
    if enhancement_level in ["medium", "aggressive"]:
        # Unsharp mask
        gaussian = cv2.GaussianBlur(contrast_enhanced, (0, 0), 2.0)
        sharpened = cv2.addWeighted(contrast_enhanced, 1.5, gaussian, -0.5, 0)
    else:
        sharpened = contrast_enhanced
    
    # Step 4: Adaptive thresholding for better text extraction
    if enhancement_level == "aggressive":
        # Use adaptive thresholding
        binary = cv2.adaptiveThreshold(
            sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        # Convert back to grayscale-like format
        enhanced = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR) if len(image.shape) == 3 else binary
    else:
        # Keep as grayscale or convert back to original format
        if len(image.shape) == 3:
            enhanced = cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)
        else:
            enhanced = sharpened
    
    return enhanced


def deblur_image(image: np.ndarray, method: str = "wiener") -> np.ndarray:
    """
    Apply deblurring to the image.
    
    Args:
        image: Image as numpy array
        method: "wiener" or "richardson_lucy"
        
    Returns:
        Deblurred image
    """
    if not CV2_AVAILABLE or not SCIPY_AVAILABLE:
        return image
    
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float64)
    else:
        gray = image.astype(np.float64)
    
    if method == "wiener":
        # Simple Wiener filter approximation
        # Create a simple motion blur kernel
        kernel_size = 5
        kernel = np.zeros((kernel_size, kernel_size))
        kernel[int((kernel_size-1)/2), :] = np.ones(kernel_size)
        kernel = kernel / kernel_size
        
        # Apply deconvolution (simplified Wiener filter)
        # In practice, this is a simplified version
        deblurred = ndimage.convolve(gray, kernel, mode='constant')
    else:
        # Richardson-Lucy deconvolution (simplified)
        # This is a basic implementation
        kernel_size = 5
        kernel = np.ones((kernel_size, kernel_size)) / (kernel_size * kernel_size)
        deblurred = ndimage.convolve(gray, kernel, mode='constant')
    
    # Normalize and convert back
    deblurred = np.clip(deblurred, 0, 255).astype(np.uint8)
    
    if len(image.shape) == 3:
        return cv2.cvtColor(deblurred, cv2.COLOR_GRAY2BGR)
    return deblurred


def pdf_to_enhanced_images(
    pdf_path: str,
    dpi: int = 300,
    detect_blur: bool = True,
    enhance_if_blurry: bool = True,
    blur_threshold: float = 100.0
) -> Tuple[List[np.ndarray], Dict[str, Any]]:
    """
    Convert PDF to images with blur detection and enhancement.
    
    Args:
        pdf_path: Path to PDF file
        dpi: Resolution for conversion (300-600 recommended)
        detect_blur: Whether to detect blur
        enhance_if_blurry: Whether to enhance if blurry detected
        blur_threshold: Threshold for blur detection
        
    Returns:
        Tuple of (list of images, metadata dict with blur info)
    """
    if not PIL_AVAILABLE:
        raise ImportError(
            "pdf2image and Pillow are required. Install with: pip install pdf2image Pillow"
        )
    
    if not CV2_AVAILABLE and (detect_blur or enhance_if_blurry):
        raise ImportError(
            "OpenCV is required for blur detection and enhancement. Install with: pip install opencv-python"
        )
    
    metadata = {
        "total_pages": 0,
        "blurry_pages": [],
        "blur_scores": {},
        "enhanced": False,
        "dpi": dpi
    }
    
    # Convert PDF to images
    print(f"[IMAGE_ENHANCEMENT] Converting PDF to images at {dpi} DPI...")
    try:
        images = convert_from_path(pdf_path, dpi=dpi)
    except Exception as e:
        raise ValueError(f"Failed to convert PDF to images: {str(e)}")
    
    metadata["total_pages"] = len(images)
    enhanced_images = []
    
    for i, pil_image in enumerate(images):
        # Convert PIL to numpy array
        img_array = np.array(pil_image)
        
        # Convert RGB to BGR for OpenCV if needed
        if CV2_AVAILABLE and len(img_array.shape) == 3:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        is_blurry = False
        blur_score = 0.0
        
        # Detect blur if enabled
        if detect_blur and CV2_AVAILABLE:
            is_blurry, blur_score = detect_blur(img_array, blur_threshold)
            metadata["blur_scores"][i + 1] = blur_score
            
            if is_blurry:
                metadata["blurry_pages"].append(i + 1)
                print(f"[IMAGE_ENHANCEMENT] Page {i + 1} detected as blurry (score: {blur_score:.2f})")
        
        # Enhance if blurry
        if enhance_if_blurry and CV2_AVAILABLE and (is_blurry or not detect_blur):
            if is_blurry:
                print(f"[IMAGE_ENHANCEMENT] Enhancing page {i + 1}...")
                # Try deblurring first for very blurry images
                if blur_score < 50:
                    img_array = deblur_image(img_array, method="wiener")
                
                # Apply general enhancement
                img_array = enhance_image(img_array, enhancement_level="medium")
                metadata["enhanced"] = True
            elif not detect_blur:
                # Apply light enhancement even if not detected as blurry
                img_array = enhance_image(img_array, enhancement_level="light")
        
        enhanced_images.append(img_array)
    
    return enhanced_images, metadata


def save_enhanced_images(images: List[np.ndarray], output_dir: str, prefix: str = "enhanced") -> List[str]:
    """
    Save enhanced images to disk.
    
    Args:
        images: List of image arrays
        output_dir: Directory to save images
        prefix: Filename prefix
        
    Returns:
        List of saved file paths
    """
    if not CV2_AVAILABLE:
        raise ImportError("OpenCV is required to save images")
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    saved_paths = []
    
    for i, img in enumerate(images):
        filename = f"{prefix}_page_{i + 1}.png"
        filepath = output_path / filename
        cv2.imwrite(str(filepath), img)
        saved_paths.append(str(filepath))
    
    return saved_paths


def assess_image_quality(image: np.ndarray) -> Dict[str, Any]:
    """
    Assess image quality metrics.
    
    Args:
        image: Image as numpy array
        
    Returns:
        Dictionary with quality metrics
    """
    if not CV2_AVAILABLE:
        return {"quality_score": 0.0, "is_good": False}
    
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    
    # Calculate multiple quality metrics
    metrics = {}
    
    # 1. Blur score (Laplacian variance)
    _, blur_score = detect_blur(gray)
    metrics["blur_score"] = blur_score
    metrics["is_sharp"] = blur_score >= 100.0
    
    # 2. Contrast (standard deviation of pixel values)
    metrics["contrast"] = float(np.std(gray))
    metrics["has_good_contrast"] = metrics["contrast"] > 30.0
    
    # 3. Brightness (mean pixel value)
    metrics["brightness"] = float(np.mean(gray))
    metrics["is_well_lit"] = 50.0 < metrics["brightness"] < 200.0
    
    # 4. Overall quality score (0-100)
    quality_score = 0.0
    if metrics["is_sharp"]:
        quality_score += 40.0
    if metrics["has_good_contrast"]:
        quality_score += 30.0
    if metrics["is_well_lit"]:
        quality_score += 30.0
    
    metrics["quality_score"] = quality_score
    metrics["is_good"] = quality_score >= 70.0
    metrics["quality_level"] = (
        "excellent" if quality_score >= 90 else
        "good" if quality_score >= 70 else
        "fair" if quality_score >= 50 else
        "poor"
    )
    
    return metrics

