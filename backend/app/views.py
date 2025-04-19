from rest_framework.decorators import api_view,throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework import status
import requests
from .models import ChatHistory
import logging
import json

logger = logging.getLogger(__name__)


@api_view(['POST'])
@throttle_classes([UserRateThrottle])  # 添加限流
def chat(request):
    try:
        # 请求参数验证
        if not request.data.get('message'):
            return Response({
                "status": "error",
                "code": "EMPTY_MESSAGE",
                "message": "消息内容不能为空"
            }, status=status.HTTP_400_BAD_REQUEST)

        # 调用 DeepSeek 模型
        ollama_response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                "model": "deepseek-r1:1.5b",
                "prompt": request.data['message'],
                "stream": True,
                "options": {"temperature": 0.7}  # 增加生成参数
            },
            stream=True,
            timeout=60
        )
        ollama_response.raise_for_status()

        def generate():
            full_response = []
            try:
                for chunk in ollama_response.iter_lines():
                    if chunk:
                        decoded_chunk = json.loads(chunk.decode())
                        content = decoded_chunk.get('response', '')
                        full_response.append(content)
                        yield json.dumps({"content": content}) + '\n'

                # 流式结束后保存完整记录
                ChatHistory.objects.create(
                    user_message=request.data['message'],
                    bot_message=''.join(full_response),
                    model_metadata={"model": "deepseek-r1:1.5b"}
                )
            except Exception as e:
                logger.error(f"保存记录失败: {str(e)}")

    except requests.exceptions.RequestException as e:
        logger.error(f"模型服务调用失败: {str(e)}", exc_info=True)
        return Response({
            "status": "error",
            "code": "MODEL_SERVICE_UNAVAILABLE",
            "message": "模型服务暂时不可用"
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    except Exception as e:
        logger.error(f"服务器内部错误: {str(e)}", exc_info=True)
        return Response({
            "status": "error",
            "code": "INTERNAL_SERVER_ERROR",
            "message": "服务器处理请求时发生错误"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)