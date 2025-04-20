from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework import status
import requests
import logging
import json
from django.http import StreamingHttpResponse
from .models import ChatHistory
import uuid
from django.db.models import Max

logger = logging.getLogger(__name__)

@api_view(['DELETE'])
def delete_conversation(request, conversation_id):
    try:
        conversation = ChatHistory.objects.get(conversation_id=conversation_id)
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
        conversation = ChatHistory.objects.get(conversation_id=conversation_id)
        return Response(conversation.messages)
    except ChatHistory.DoesNotExist:
        return Response({'error': f'找不到 ID 为 {conversation_id} 的对话'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"获取对话 {conversation_id} 详情失败: {e}")
        return Response({'error': f'获取对话 {conversation_id} 详情时发生错误: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_chat_history(request):
    try:
        # 获取每个 conversation_id 的最新记录，并使用第一条用户消息作为标题
        unique_conversations = ChatHistory.objects.values('conversation_id').annotate(latest_timestamp=Max('timestamp')).order_by('-latest_timestamp')[:20]
        history = ChatHistory.objects.filter(conversation_id__in=[item['conversation_id'] for item in unique_conversations]).order_by('-timestamp')

        formatted_history = []
        for item in history:
            title = f"新对话 {item.conversation_id}"
            if item.messages and len(item.messages) > 0 and item.messages[0].get('sender') == 'user':
                title = f"用户: {item.messages[0].get('content', '')[:30]}..."
            elif item.messages and len(item.messages) > 0:
                # 如果第一条不是用户消息，尝试查找第一条用户消息
                for msg in item.messages:
                    if msg.get('sender') == 'user':
                        title = f"用户: {msg.get('content', '')[:30]}..."
                        break

            formatted_history.append({'id': str(item.conversation_id), 'title': title, 'timestamp': item.timestamp})
        return Response(formatted_history)
    except Exception as e:
        logger.error(f"获取聊天历史失败: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@throttle_classes([UserRateThrottle])
def chat(request):
    user_message = request.data.get('message')
    conversation_id_str = request.data.get('conversation_id')

    if not user_message:
        return Response({"status": "error", "code": "EMPTY_MESSAGE", "message": "消息内容不能为空"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        ollama_response = requests.post(
            'http://localhost:11434/api/generate',
            json={"model": "deepseek-r1:1.5b", "prompt": user_message, "stream": True, "options": {"temperature": 0.7}},
            stream=True,
            timeout=60
        )
        ollama_response.raise_for_status()

        def generate():
            nonlocal conversation_id_str
            full_response = []
            try:
                for chunk in ollama_response.iter_lines():
                    if chunk:
                        decoded_chunk = json.loads(chunk.decode())
                        content = decoded_chunk.get('response', '')
                        full_response.append(content)
                        yield f"data: {json.dumps({'content': content})}\n\n"

                bot_message = ''.join(full_response)
                message_data = {"sender": "bot", "content": bot_message}
                user_message_data = {"sender": "user", "content": user_message}

                if conversation_id_str:
                    try:
                        conversation_id = uuid.UUID(conversation_id_str)
                        chat_history = ChatHistory.objects.get(conversation_id=conversation_id)
                        chat_history.messages.append(user_message_data)
                        chat_history.messages.append(message_data)
                        chat_history.save()
                    except ChatHistory.DoesNotExist:
                        new_chat_history = ChatHistory.objects.create(
                            messages=[user_message_data, message_data],
                            model_metadata={"model": "deepseek-r1:1.5b"}
                        )
                        conversation_id_str = str(new_chat_history.conversation_id)
                else:
                    new_chat_history = ChatHistory.objects.create(
                        messages=[user_message_data, message_data],
                        model_metadata={"model": "deepseek-r1:1.5b"}
                    )
                    conversation_id_str = str(new_chat_history.conversation_id)

            except Exception as e:
                logger.error(f"保存/更新对话记录失败: {e}")
            finally:
                ollama_response.close()

        response = StreamingHttpResponse(generate(), content_type='text/event-stream')
        response['X-Conversation-ID'] = conversation_id_str
        return response

    except requests.exceptions.RequestException as e:
        logger.error(f"模型服务调用失败: {e}", exc_info=True)
        return Response({
            "status": "error",
            "code": "MODEL_SERVICE_UNAVAILABLE",
            "message": "模型服务暂时不可用"
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    except Exception as e:
        logger.error(f"服务器内部错误: {e}", exc_info=True)
        return Response({
            "status": "error",
            "code": "INTERNAL_SERVER_ERROR",
            "message": "服务器处理请求时发生错误"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)