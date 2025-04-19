from django.urls import path
from . import views

urlpatterns = [
    path('chat/', views.chat, name='chat'),
    path('history/', views.get_chat_history, name='chat_history'),
    path('history/<int:conversation_id>/', views.get_conversation_detail, name='conversation_detail'),
path('history/<int:conversation_id>/delete/', views.delete_conversation, name='delete_conversation'),
]