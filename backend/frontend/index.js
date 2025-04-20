const historyList = document.getElementById('history-list');
const messageContainer = document.getElementById('message-container');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');
const API_ENDPOINT_CHAT = '/api/chat/';
const API_ENDPOINT_HISTORY = '/api/history/';

let currentConversationId = null; // 用于跟踪当前选中的对话 ID
let currentBotMessageElement = null; // 用于跟踪当前正在接收流数据的 bot 消息元素
const newChatButton = document.getElementById('new-chat-button');

// 加载历史对话列表
async function loadChatHistory() {
    try {
        const response = await fetch(API_ENDPOINT_HISTORY);
        if (!response.ok) {
            console.error('Failed to load chat history:', response.status);
            return;
        }
        const history = await response.json();
        displayChatHistory(history);
    } catch (error) {
        console.error('Error loading chat history:', error);
    }
}

// 显示历史对话列表
function displayChatHistory(history) {
    historyList.innerHTML = '';
    history.forEach(item => {
        const listItem = document.createElement('li');
        let displayText = item.title || `对话 ${item.id}`;
        if (item.timestamp) {
            const formattedTime = new Date(item.timestamp).toLocaleString();
            displayText += ` (${formattedTime})`;
        }
        listItem.textContent = displayText;
        listItem.dataset.conversationId = item.id;
        listItem.addEventListener('click', loadConversation);

        const deleteButton = document.createElement('button');
        deleteButton.textContent = '删除';
        deleteButton.classList.add('delete-button'); // 添加删除按钮的 CSS 类
        deleteButton.addEventListener('click', (event) => {
            event.stopPropagation(); // 阻止点击事件冒泡到列表项
            deleteChatHistoryItem(item.id, listItem);
        });

        listItem.appendChild(deleteButton);
        historyList.appendChild(listItem);
    });
}

async function deleteChatHistoryItem(conversationId, listItemElement) {
    const API_ENDPOINT_DELETE = `/api/history/${conversationId}/delete/`;

    if (confirm(`确定要删除对话 ${conversationId} 吗？`)) {
        try {
            const response = await fetch(API_ENDPOINT_DELETE, {
                method: 'DELETE',
            });

            if (response.ok) {
                listItemElement.remove(); // 从列表中移除已删除的项
                if (currentConversationId === conversationId) {
                    messageContainer.innerHTML = ''; // 如果当前是已删除的对话，则清空消息区域
                    currentConversationId = null;
                }
                console.log(`对话 ${conversationId} 删除成功`);
            } else {
                const errorData = await response.json();
                console.error(`删除对话 ${conversationId} 失败:`, errorData);
                alert(`删除对话 ${conversationId} 失败: ${errorData.error || '未知错误'}`);
            }
        } catch (error) {
            console.error('删除对话时发生错误:', error);
            alert(`删除对话 ${conversationId} 时发生错误: ${error}`);
        }
    }
}

function startNewChat() {
    messageContainer.innerHTML = ''; // 清空聊天消息
    currentConversationId = null; // 重置当前对话 ID
    userInput.value = '';
    document.querySelectorAll('#history-list li.active').forEach(item => {
        item.classList.remove('active');
    });
    displayMessage('开始新的对话', 'bot-system');
    loadChatHistory();
}

newChatButton.addEventListener('click', startNewChat);

// 加载选定的历史对话
async function loadConversation(event) {
    document.querySelectorAll('#history-list li.active').forEach(item => {
        item.classList.remove('active');
    });
    event.target.classList.add('active');

    currentConversationId = event.target.dataset.conversationId;
    const conversationId = event.target.dataset.conversationId;
    const API_ENDPOINT_CONVERSATION = `/api/history/${conversationId}/`;
    messageContainer.innerHTML = '';
    try {
        const response = await fetch(API_ENDPOINT_CONVERSATION);
        if (!response.ok) {
            console.error(`Failed to load conversation ${conversationId}:`, response.status);
            return;
        }
        const conversation = await response.json();
        displayConversation(conversation);
    } catch (error) {
        console.error(`Error loading conversation ${conversationId}:`, error);
    }
}

// 显示选定的历史对话
function displayConversation(conversation) {
    conversation.forEach(message => {
        displayMessage(message.content, message.sender);
    });
    scrollToBottom();
}

// 显示普通消息
function displayMessage(message, sender) {
    const filteredMessage = message.replace(/<\/?think>/g, '');
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', `${sender}-message`);
    messageDiv.textContent = filteredMessage;
    messageContainer.appendChild(messageDiv);
    scrollToBottom();
}

// 显示流式消息内容
function displayStreamedMessage(content) {
    const filteredContent = content.replace(/<\/?think>/g, '');
    if (currentBotMessageElement) {
        currentBotMessageElement.textContent += filteredContent;
        scrollToBottom();
    }
}

// 发送消息
async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    displayMessage(message, 'user');
    userInput.value = '';

    currentBotMessageElement = document.createElement('div');
    currentBotMessageElement.classList.add('message', 'bot-message');
    currentBotMessageElement.dataset.isStreaming = 'true';
    messageContainer.appendChild(currentBotMessageElement);
    scrollToBottom();

    try {
        const response = await fetch(API_ENDPOINT_CHAT, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                conversation_id: currentConversationId
            }),
        });

        const newConversationId = response.headers.get('X-Conversation-ID');
        if (newConversationId && !currentConversationId) {
            currentConversationId = newConversationId;
        }

        if (!response.ok) {
            const errorData = await response.json();
            displayMessage(`Error: ${errorData.message || 'Failed to send message'}`, 'bot-error');
            console.error('Failed to send message:', response.status, errorData);
            currentBotMessageElement = null;
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let partialBotMessage = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) {
                if (currentBotMessageElement) {
                    currentBotMessageElement.dataset.isStreaming = 'false';
                }
                currentBotMessageElement = null;
                loadChatHistory(); // 在会话结束后重新加载历史记录
                break;
            }
            partialBotMessage += decoder.decode(value);
            const lines = partialBotMessage.split('\n\n');
            partialBotMessage = lines.pop();

            lines.forEach(line => {
                if (line.startsWith('data:')) {
                    try {
                        const jsonData = JSON.parse(line.substring(5).trim());
                        if (jsonData.content) {
                            displayStreamedMessage(jsonData.content);
                        }
                    } catch (error) {
                        console.error('Error parsing SSE data:', error, line);
                    }
                }
            });
        }

    } catch (error) {
        displayMessage(`Error: ${error}`, 'bot-error');
        console.error('Error sending message:', error);
        if (currentBotMessageElement) {
            currentBotMessageElement.dataset.isStreaming = 'false';
            currentBotMessageElement.textContent = 'Error loading response.';
            currentBotMessageElement = null;
        }
    } finally {
        scrollToBottom();
    }
}

function scrollToBottom() {
    messageContainer.scrollTop = messageContainer.scrollHeight;
}

// 事件监听
sendButton.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (event) => {
    if (event.key === 'Enter') {
        sendMessage();
    }
});

// 页面加载时加载历史对话
loadChatHistory();
scrollToBottom();