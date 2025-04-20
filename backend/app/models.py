from django.db import models
import uuid
import json

class ChatHistory(models.Model):
    conversation_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="对话ID")
    messages = models.JSONField(default=list, verbose_name="对话消息")  # 存储消息列表，例如 [{"sender": "user", "content": "..."}, {"sender": "bot", "content": "..."}]
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="时间戳")
    model_metadata = models.JSONField(default=dict, verbose_name="模型元数据")

    def __str__(self):
        return f"对话 {self.conversation_id} 于 {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

    class Meta:
        ordering = ['-timestamp']
        verbose_name = '聊天记录'
        verbose_name_plural = '聊天记录'
        indexes = [
            models.Index(fields=['conversation_id']),
            models.Index(fields=['timestamp']),
        ]