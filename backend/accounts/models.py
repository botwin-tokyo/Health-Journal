import uuid

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class AccountManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, *args, **kwargs):
        raise ValueError("Use operator invitation enrollment; public admin is disabled")


class Account(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=[("owner", "Owner"), ("doctor", "Doctor")])
    enrollment_complete = models.BooleanField(default=False)
    security_epoch = models.UUIDField(default=uuid.uuid4, editable=False)
    sharing_epoch = models.PositiveBigIntegerField(default=0, editable=False)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = AccountManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="account_email_case_unique"),
            models.UniqueConstraint(
                fields=["role"], condition=models.Q(role="owner"), name="one_owner"
            ),
            models.CheckConstraint(
                condition=models.Q(role__in=["owner", "doctor"]), name="known_role"
            ),
        ]


class Invitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, null=True)
    email = models.EmailField()
    role = models.CharField(max_length=10, choices=[("owner", "Owner"), ("doctor", "Doctor")])
    secret_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class SessionSecurity(models.Model):
    session_hash = models.CharField(primary_key=True, max_length=64)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    security_epoch = models.UUIDField()
    created_at = models.DateTimeField()
    last_user_activity_at = models.DateTimeField()
    idle_expires_at = models.DateTimeField()
    absolute_expires_at = models.DateTimeField()
    password_verified_at = models.DateTimeField()
