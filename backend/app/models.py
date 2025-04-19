from django.db import models
import json

class ChatHistory(models.Model):
    user_message = models.TextField(verbose_name="用户消息")
    bot_message = models.TextField(verbose_name="机器人回复")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="时间戳")
    model_metadata = models.JSONField(verbose_name="模型元数据", default=dict)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = '聊天记录'
        indexes = [
            models.Index(fields=['timestamp']),
        ]

    def get_model_stats(self):
        """解析模型元数据"""
        return {
            'response_time': self.model_metadata.get('response_time', 0),
            'tokens_used': self.model_metadata.get('tokens_used', 0)
        }