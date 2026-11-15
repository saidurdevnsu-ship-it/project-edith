import uuid
import secrets
import hashlib
from django.db import models
from django.utils import timezone


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, default='New Conversation')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.title} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"


class ChatMessage(models.Model):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ]

    conversation = models.ForeignKey(
        Conversation,
        related_name='messages',
        on_delete=models.CASCADE
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    model = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"[{self.role}] {self.content[:30]}..."


class EdithAPIKey(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, default='Default Key')
    prefix = models.CharField(max_length=30)
    hashed_key = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.prefix})"

    @classmethod
    def generate(cls, name: str = 'Default Key'):
        """Generates a secure edith_sk_ key, stores the hash, and returns the raw key once."""
        raw_token = secrets.token_hex(20)
        raw_key = f"edith_sk_{raw_token}"
        prefix = f"{raw_key[:12]}...{raw_key[-4:]}"
        hashed = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
        key_obj = cls.objects.create(
            name=name.strip() or 'Default Key',
            prefix=prefix,
            hashed_key=hashed,
            is_active=True
        )
        return key_obj, raw_key

    @classmethod
    def verify(cls, raw_key: str):
        """Verifies if the raw API key is valid and active."""
        if not raw_key:
            return None
        hashed = hashlib.sha256(raw_key.strip().encode('utf-8')).hexdigest()
        try:
            key_obj = cls.objects.get(hashed_key=hashed, is_active=True)
            key_obj.last_used_at = timezone.now()
            key_obj.save(update_fields=['last_used_at'])
            return key_obj
        except cls.DoesNotExist:
            return None
