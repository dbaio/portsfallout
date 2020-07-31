from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=64, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Categories"


class Port(models.Model):
    origin = models.CharField(max_length=128, unique=True)
    name = models.CharField(max_length=64)
    comment = models.CharField(max_length=192, blank=True)
    maintainer = models.EmailField()
    www = models.URLField(blank=True)

    # Categories
    main_category = models.CharField(max_length=64)
    categories = models.ManyToManyField(Category)

    def __str__(self):
        return self.origin


class Fallout(models.Model):
    port = models.ForeignKey(Port, on_delete=models.CASCADE)
    env = models.CharField(max_length=48)
    version = models.CharField(max_length=24)
    category = models.CharField(max_length=48)
    maintainer = models.EmailField()
    last_committer = models.EmailField()
    date = models.DateTimeField()
    log_url = models.URLField()
    build_url = models.URLField()
    report_url = models.URLField()
    server = models.CharField(max_length=48, blank=True)

    def __str__(self):
        # head-arm64-default | net/findomain
        return self.env + " | " + self.port.origin

