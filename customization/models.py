from django.db import models
from django.contrib.auth.models import User


class Product(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    VIEW_CHOICES = [
        ('front', 'Front'),
        ('back', 'Back'),
        ('side', 'Side'),
    ]
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image_file = models.ImageField(upload_to='products/')
    view = models.CharField(max_length=10, choices=VIEW_CHOICES)
    print_area_x = models.IntegerField()  # x coordinate of print area
    print_area_y = models.IntegerField()  # y coordinate
    print_area_width = models.IntegerField()
    print_area_height = models.IntegerField()

    def save(self, *args, **kwargs):
        # Delete old image file when updating
        if self.pk:
            try:
                old_instance = ProductImage.objects.get(pk=self.pk)
                if old_instance.image_file and old_instance.image_file != self.image_file:
                    old_instance.image_file.delete(save=False)
            except ProductImage.DoesNotExist:
                pass
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} - {self.view}"


class UserDesign(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    design_image = models.ImageField(upload_to='designs/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Design by {self.user.username} at {self.uploaded_at}"


class RenderedImage(models.Model):
    user_design = models.ForeignKey(UserDesign, on_delete=models.CASCADE)
    product_image = models.ForeignKey(ProductImage, on_delete=models.CASCADE)
    rendered_file = models.ImageField(upload_to='rendered/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Rendered {self.user_design} on {self.product_image}"