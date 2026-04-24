from django.contrib import admin
from .models import Product, ProductImage, UserDesign, RenderedImage

admin.site.register(Product)
admin.site.register(ProductImage)
admin.site.register(UserDesign)
admin.site.register(RenderedImage)