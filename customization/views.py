from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import UserDesign, RenderedImage
from .tasks import render_design_on_products

def frontend_view(request):
    return render(request, 'index.html')


@csrf_exempt
def upload_design(request):
    if request.method == 'POST':
        design_image = request.FILES.get('design_image')
        if not design_image:
            return JsonResponse({'error': 'No design image provided'}, status=400)
        
        # Assume user is authenticated, or handle accordingly
        user = request.user if request.user.is_authenticated else None
        if not user:
            return JsonResponse({'error': 'User not authenticated'}, status=401)
        
        user_design = UserDesign.objects.create(user=user, design_image=design_image)
        
        # Trigger Celery task
        render_design_on_products.delay(user_design.id)
        
        return JsonResponse({'design_id': user_design.id, 'message': 'Design uploaded and processing started'})
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


def get_rendered_images(request, design_id):
    try:
        user_design = UserDesign.objects.get(id=design_id)
        rendered_images = RenderedImage.objects.filter(user_design=user_design)
        data = [
            {
                'product_view': ri.product_image.view,
                'rendered_url': ri.rendered_file.url,
                'created_at': ri.created_at.isoformat()
            }
            for ri in rendered_images
        ]
        return JsonResponse({'rendered_images': data})
    except UserDesign.DoesNotExist:
        return JsonResponse({'error': 'Design not found'}, status=404)