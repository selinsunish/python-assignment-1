import cv2
import numpy as np
import os


def process_design_on_product(design_path, product_image_obj, output_path):
    try:
        print("🔥 MAXIMUM REALISM IMAGE PROCESSING RUNNING")

        # ================================
        # 1️⃣ RESOLVE PATHS SAFELY
        # ================================
        design_path = os.path.abspath(design_path)

        # CHANGE THIS IF YOUR FIELD NAME IS DIFFERENT
        product_path = product_image_obj.image_file.path

        print("Design path:", design_path)
        print("Product path:", product_path)

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

        print(f"Design image shape: {design.shape}, size: {design.size}")
        print(f"Product image shape: {product_img.shape}, size: {product_img.size}")

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

        print(f"Print area: x={x}, y={y}, w={w}, h={h}")
        print(f"Product image dimensions: height={product_img.shape[0]}, width={product_img.shape[1]}")

        if x < 0 or y < 0 or w <= 0 or h <= 0:
            raise ValueError("Invalid print area: negative or zero dimensions")

        if x + w > product_img.shape[1] or y + h > product_img.shape[0]:
            raise ValueError("Print area exceeds product image bounds")

        # ================================
        # 6️⃣ RESIZE DESIGN
        # ================================
        design_resized = cv2.resize(design, (w, h), interpolation=cv2.INTER_LINEAR)

        # ================================
        # 6️⃣ RESIZE DESIGN
        # ================================
        design_resized = cv2.resize(design, (w, h), interpolation=cv2.INTER_LINEAR)

        # ================================
        # 7️⃣ HANDLE ALPHA / BACKGROUND REMOVAL
        # ================================
        if design_resized.shape[2] == 4:  # RGBA
            design_rgb = design_resized[:, :, :3].astype(np.float32)
            alpha = design_resized[:, :, 3].astype(np.float32) / 255.0

        else:
            design_rgb = design_resized.astype(np.float32)
            alpha = None

        if alpha is None:
            # Try to remove a uniform background from RGB-only designs.
            gray_design = cv2.cvtColor(design_resized, cv2.COLOR_BGR2GRAY)
            # Threshold to find near-white / light background.
            _, mask = cv2.threshold(gray_design, 240, 255, cv2.THRESH_BINARY_INV)
            mask = cv2.GaussianBlur(mask, (7, 7), 0)
            alpha = mask.astype(np.float32) / 255.0

            # Make sure fully transparent areas are hidden.
            alpha = np.clip(alpha, 0.0, 1.0)

        # Ensure alpha is float32 and same size as design
        alpha = alpha.astype(np.float32)
        if alpha.ndim == 2:
            alpha = alpha

        # Optional: Fill transparent parts with white behind the logo for better blending.
        white_bg = np.full_like(design_rgb, 255.0, dtype=np.float32)
        design_rgb = design_rgb * alpha[:, :, np.newaxis] + white_bg * (1 - alpha[:, :, np.newaxis])

        # ================================
        # 8️⃣ PERSPECTIVE WARP
        # ================================
        src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        dst = np.float32([
            [0, 0],
            [w * 0.9, 10],
            [w, h],
            [w * 0.1, h - 10]
        ])

        M = cv2.getPerspectiveTransform(src, dst)

        warped_rgb = cv2.warpPerspective(design_rgb, M, (w, h), borderMode=cv2.BORDER_REFLECT)
        warped_alpha = cv2.warpPerspective(alpha, M, (w, h), borderMode=cv2.BORDER_REFLECT)

        warped_alpha = cv2.GaussianBlur(warped_alpha, (7, 7), 0) * 0.95

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

        print(f"ROI shape: {roi.shape}, size: {roi.size}")

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

        print("✅ Saved (NO TRANSPARENCY):", output_path)

        return output_path

    except Exception as e:
        raise ValueError(f"Processing failed: {str(e)}")