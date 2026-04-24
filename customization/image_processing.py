import cv2
import numpy as np
import os


def process_design_on_product(design_path, product_image_obj, output_path):
    try:

        # ================================
        # 1️⃣ RESOLVE PATHS SAFELY
        # ================================
        design_path = os.path.abspath(design_path)

        # CHANGE THIS IF YOUR FIELD NAME IS DIFFERENT
        product_path = product_image_obj.image_file.path

        # ================================
        # 2️⃣ VALIDATE FILES EXIST
        # ================================
        if not os.path.exists(design_path):
            raise ValueError(f"Design file not found: {design_path}")

        if not os.path.exists(product_path):
            raise ValueError(f"Product file not found: {product_path}")

        # ================================
        # 3️⃣ LOAD IMAGES SAFELY
        # ================================
        design = cv2.imread(design_path, cv2.IMREAD_UNCHANGED)
        product_img = cv2.imread(product_path)

        if design is None or design.size == 0:
            raise ValueError(f"OpenCV failed to load DESIGN image: {design_path}")

        if product_img is None or product_img.size == 0:
            raise ValueError(f"OpenCV failed to load PRODUCT image: {product_path}")

        # ================================
        # 4️⃣ FORCE FRESH DJANGO OBJECT (IMPORTANT)
        # ================================
        product_image_obj = product_image_obj.__class__.objects.get(
            id=product_image_obj.id
        )

        # ================================
        # 5️⃣ PRINT AREA VALIDATION
        # ================================
        x = product_image_obj.print_area_x
        y = product_image_obj.print_area_y
        w = product_image_obj.print_area_width
        h = product_image_obj.print_area_height

        if x < 0 or y < 0 or w <= 0 or h <= 0:
            raise ValueError("Invalid print area: negative or zero dimensions")

        if x + w > product_img.shape[1] or y + h > product_img.shape[0]:
            raise ValueError("Print area exceeds product image bounds")

        # ================================
        # 6️⃣ RESIZE DESIGN (PRESERVING ASPECT RATIO)
        # ================================
        orig_h, orig_w = design.shape[:2]
        scale = min(w / orig_w, h / orig_h)
        new_w, new_h = int(orig_w * scale), int(orig_h * scale)
        
        design_scaled = cv2.resize(design, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        
        # ================================
        # 7️⃣ HANDLE ALPHA / BACKGROUND REMOVAL (ON SCALED DESIGN)
        # ================================
        if len(design_scaled.shape) == 3 and design_scaled.shape[2] == 4:  # RGBA
            scaled_rgb = design_scaled[:, :, :3].astype(np.float32)
            scaled_alpha = design_scaled[:, :, 3].astype(np.float32) / 255.0
        else:
            if len(design_scaled.shape) == 2:
                scaled_rgb = cv2.cvtColor(design_scaled, cv2.COLOR_GRAY2BGR).astype(np.float32)
                gray_design = design_scaled
            else:
                scaled_rgb = design_scaled.astype(np.float32)
                gray_design = cv2.cvtColor(design_scaled, cv2.COLOR_BGR2GRAY)
            
            # Threshold to find near-white / light background.
            _, mask = cv2.threshold(gray_design, 240, 255, cv2.THRESH_BINARY_INV)
            mask = cv2.GaussianBlur(mask, (7, 7), 0)
            scaled_alpha = mask.astype(np.float32) / 255.0
            scaled_alpha = np.clip(scaled_alpha, 0.0, 1.0)

        # ================================
        # 7.5️⃣ PAD INTO TARGET (W, H)
        # ================================
        # Create empty transparent canvas (h, w)
        design_rgb = np.zeros((h, w, 3), dtype=np.float32)
        alpha = np.zeros((h, w), dtype=np.float32)

        # Ensure alpha is float32 and same size as design
        alpha = alpha.astype(np.float32)

        # Center coordinates
        y_offset = (h - new_h) // 2
        x_offset = (w - new_w) // 2

        # Paste the scaled design and alpha into the center
        design_rgb[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = scaled_rgb
        alpha[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = scaled_alpha

        # ================================
        # 8️⃣ NO PERSPECTIVE WARP (FLAT OVERLAY)
        # ================================
        warped_rgb = design_rgb
        warped_alpha = alpha
        
        # Soften edges slightly
        warped_alpha = cv2.GaussianBlur(warped_alpha, (3, 3), 0) * 0.95

        # ================================
        # 9️⃣ SATURATION BOOST
        # ================================
        hsv = cv2.cvtColor(warped_rgb.astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.3, 0, 255)
        warped_rgb = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)

        # ================================
        # 🔟 ROI EXTRACTION
        # ================================
        roi = product_img[y:y + h, x:x + w].astype(np.float32)

        if roi.size == 0:
            raise ValueError("ROI is empty - print area out of bounds")

        try:
            gray = cv2.cvtColor(roi.astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        except cv2.error as e:
            raise ValueError(f"cvtColor failed on ROI: {e}")

        brightness = 0.5 + 0.5 * gray

        # ================================
        # 1️⃣1️⃣ TEXTURE EFFECT
        # ================================
        texture = cv2.GaussianBlur(gray, (7, 7), 0) * 0.1

        for c in range(3):
            warped_rgb[:, :, c] = warped_rgb[:, :, c] * (1 - texture)

        warped_rgb = warped_rgb * brightness[:, :, np.newaxis]

        # ================================
        # 1️⃣2️⃣ BLENDING (ENSURE OPAQUE OUTPUT)
        # ================================
        blended = np.zeros_like(roi, dtype=np.float32)

        for c in range(3):
            blended[:, :, c] = (
                warped_alpha * warped_rgb[:, :, c] +
                (1 - warped_alpha) * roi[:, :, c]
            )

        blended = np.clip(blended, 0, 255).astype(np.uint8)

        # ================================
        # 1️⃣3️⃣ SHARPEN
        # ================================
        blurred = cv2.GaussianBlur(blended, (0, 0), 1.2)
        blended = cv2.addWeighted(blended, 1.3, blurred, -0.3, 0)
        blended = np.clip(blended, 0, 255).astype(np.uint8)

        # ================================
        # 1️⃣4️⃣ PUT BACK INTO IMAGE (ENSURE NO ALPHA LEAKAGE)
        # ================================
        product_img[y:y + h, x:x + w] = blended

        # ================================
        # 1️⃣5️⃣ SAVE OUTPUT (WITH OPAQUE BACKGROUND)
        # ================================
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        success = cv2.imwrite(output_path, product_img)

        if not success:
            raise IOError("Failed to save output image")

        return output_path

    except Exception as e:
        raise ValueError(f"Processing failed: {str(e)}")