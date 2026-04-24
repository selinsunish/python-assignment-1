from django.urls import path
from . import views

urlpatterns = [
    path('upload-design/', views.upload_design, name='upload_design'),
    path('rendered-images/<int:design_id>/', views.get_rendered_images, name='get_rendered_images'),
]