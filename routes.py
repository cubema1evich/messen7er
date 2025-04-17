from views import *

routes = {
    '/static/': View,
    '^/favicon.ico$': View,
    '^/$': IndexView,  
    '/get_user_id': GetUserIdView,
    '/get_messages': GetMessageView,
    '/send_message': SendMessageView,
    '/register': RegisterView,
    '/login': LoginView,
    '/get_group_messages': GetGroupMessagesView,
    '/create_group': CreateGroupView,
    '/add_to_group': AddToGroupView,
    '/leave_group': LeaveGroupView,
    '/get_groups': GetGroupsView,
    '/send_private_message': SendPrivateMessageView,
    '/get_private_messages': GetPrivateMessagesView,
    '/search_users': SearchUsersView,
    '/get_private_chats': GetPrivateChatsView,
    '/search_messages': SearchMessagesView,
    '/get_group_members': GetGroupMembersView,
    '/get_general_chat_members': GetGeneralMembersView,
    '/send_system_message': SendSystemMessageView,
    r'^/delete_message/(\d+)$': DeleteMessageView,
    r'^/404$': NotFoundView,
    r'^/403$': ForbiddenView,
    r'^/500$': InternalServerErrorView
}


def route(url):
    """
    Преобразовывает URL в путь к файлу в соответствии с определенными маршрутами.
    """
    for key in routes.keys():
        if url.startswith(key):
            return routes[key] + url[len(key):]
        return url