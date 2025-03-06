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
    '/get_groups': GetGroupsView
}


def route(url):
    """
    Преобразовывает URL в путь к файлу в соответствии с определенными маршрутами.
    """
    for key in routes.keys():
        if url.startswith(key):
            return routes[key] + url[len(key):]
        return url