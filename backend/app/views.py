from rest_framework.decorators import api_view,throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework import status
import requests
from .models import ChatHistory
import logging
import json
from django.http import StreamingHttpResponse  # 导入 StreamingHttpResponse

logger = logging.getLogger(__name__)

@api_view(['DELETE'])
def delete_conversation(request, conversation_id):
    try:
        conversation = ChatHistory.objects.get(id=conversation_id)
        conversation.delete()
        return Response({'message': f'对话 {conversation_id} 已成功删除'}, status=status.HTTP_200_OK)
    except ChatHistory.DoesNotExist:
        return Response({'error': f'找不到 ID 为 {conversation_id} 的对话'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"删除对话 {conversation_id} 失败: {str(e)}")
        return Response({'error': f'删除对话 {conversation_id} 时发生错误: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_conversation_detail(request, conversation_id):
    try:
        conversation = ChatHistory.objects.filter(id=conversation_id).order_by('timestamp').values('user_message', 'bot_message')
        return Response(list(conversation))
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
def get_chat_history(request):
    try:
        history = ChatHistory.objects.order_by('-timestamp').values('id', 'user_message', 'bot_message', 'timestamp')[:20] # 获取最近的 20 条记录，可以根据你的需求调整
        # 可以根据你的需求格式化返回的数据，例如提取一个简单的对话标题
        formatted_history = []
        for item in history:
            title = f"用户: {item['user_message'][:20]}... | 机器人: {item['bot_message'][:20]}..." if item['user_message'] and item['bot_message'] else f"对话 ID: {item['id']}"
            formatted_history.append({'id': item['id'], 'title': title})
        return Response(formatted_history)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


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
                        yield f"data: {json.dumps({'content': content})}\n\n"  # SSE格式

                # 流式结束后保存完整记录
                ChatHistory.objects.create(
                    user_message=request.data['message'],
                    bot_message=''.join(full_response),
                    model_metadata={"model": "deepseek-r1:1.5b"}
                )
            except Exception as e:
                logger.error(f"保存记录失败: {str(e)}")
            finally:
                ollama_response.close() # 确保关闭连接

        return StreamingHttpResponse(generate(), content_type='text/event-stream')

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