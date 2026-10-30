from uuid import uuid4
from django.db import models
from django.contrib.auth.models import AbstractUser


class Account(AbstractUser):
    """Custom User Model"""
    id = models.UUIDField(default=uuid4, editable=False, primary_key=True)
    telephone = models.CharField(max_length=10, null=True, blank=True)
    user_type = models.CharField(
        max_length=20,
        choices=(
            ("ADMIN", "ADMIN"),
            ("SALEPERSON", "SALEPERSON"),
        ),
        default="ADMIN",
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.username}"

    @property
    def full_name(self):
        """Return full name"""
        return f"{self.last_name} {self.first_name}"
