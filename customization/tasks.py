from celery import shared_task
from .models import UserDesign, ProductImage, RenderedImage
from .image_processing import process_design_on_product
import os
from django.conf import settings


@shared_task
def render_design_on_products(design_id):
    try:
        user_design = UserDesign.objects.get(id=design_id)
        product_images = ProductImage.objects.all()
        
        # 🔥 Ensure folder exists HERE (important)
        output_dir = os.path.join(settings.MEDIA_ROOT, 'rendered')
        os.makedirs(output_dir, exist_ok=True)
        
        for product_image in product_images:
            rendered_file_name = f"rendered_{design_id}_{product_image.id}.png"
            
            output_path = os.path.join(output_dir, rendered_file_name)
            
            # Process image
            process_design_on_product(
                user_design.design_image.path,
                product_image,
                output_path
            )
            
            # Save DB entry
            RenderedImage.objects.create(
                user_design=user_design,
                product_image=product_image,
                rendered_file=f"rendered/{rendered_file_name}"
            )

    except UserDesign.DoesNotExist:
        print(f"UserDesign with id {design_id} does not exist")
    except Exception as e:
        print(f"Error in render_design_on_products: {e}")